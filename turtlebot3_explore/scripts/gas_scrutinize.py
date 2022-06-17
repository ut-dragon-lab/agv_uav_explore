#!/usr/bin/env python
import imp
import rospy
import message_filters
import math
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist, PoseStamped, Pose
from std_msgs.msg import Float32, Bool
from turtlebot3_explore.msg import PositionAndGas
from nav_msgs.msg import Odometry
from move_base_msgs.msg import MoveBaseActionGoal
from nav_msgs.msg import OccupancyGrid
import numpy as np

# if scan_val is Inf, inf_distance is assigned.
inf_distance = 5.0
# the radius of the robot explore area
territory_radius = 0.6
# the velocity of exploring and the type of explore state
explore_vel = 0.3
explore_time = 0.3
explore_yaw_vel = 1.0
explore_yaw_time = 0.3
explore_state = ['front', 'back', 'turn', 'after_turn', 'explored']
limit_time = 30.0

class gas_scrutinize:
    def __init__(self):

        rospy.init_node("gas_scrutinize")

        self.vel_pub = rospy.Publisher("/cmd_vel", Twist, queue_size=10)
        self.goal_pub = rospy.Publisher("/move_base_simple/goal", PoseStamped, queue_size=10)
        self.scan_sub = rospy.Subscriber("/scan", LaserScan, self.callback)
        self.gas_value_sub = rospy.Subscriber("/gas", Float32, self.gas_callback)
        self.odom_sub = rospy.Subscriber("/odom", Odometry, self.odom_callback)
        
        self.is_finish_search_sub = rospy.Subscriber("/is_finish_search", Bool, self.search_callback)
        self.execute = False
        
        # self.estimated_gas_map_sub = rospy.Subscriber("estimated_gas_map", self.map_callback)

        self.timeout_sec = rospy.get_param("~timeout_sec", 15.0)

        self.start_time = 0
        self.max_gas_value = 0.0
        self.final_robot_pose = Pose()
        self.robot_pose = Pose()
        self.goal_pose = PoseStamped()
        self.goal_pose.header.frame_id = "map"
        self.cmd_x = 0.0
        self.cmd_yaw = 0.0
        self.explore_state = 'front'
        self.iscorrect_path = True

        rospy.spin()

    def search_callback(self, msg):
        if msg.data == true:
            self.execute = True

    def odom_callback(self, msg):
        self.robot_pose = msg.pose.pose

    def gas_callback(self,msg):
        if msg.data > self.max_gas_value:
            self.max_gas_value = msg.data
            self.final_robot_pose = self.robot_pose
            self.max_gas_value.time = rospy.get_time()

    def explore(self):
        if self.explore_state == 'front':
            self.cmd_x = explore_vel
            self.cmd_yaw = 0.0
            self.explore_state = 'back'
        elif self.explore_state == 'back':
            rospy.sleep(explore_time)
            self.cmd_x = -1.0*explore_vel
            self.explore_state = 'turn'
        elif self.explore_state == 'turn':
            rospy.sleep(explore_time)
            self.cmd_x = 0.0
            self.cmd_yaw = explore_yaw_vel
            self.explore_state = 'after_turn'
        elif self.explore_state == 'after_turn':
            rospy.sleep(explore_yaw_time)
            self.cmd_x = 0.0
            self.cmd_yaw = 0.0
            self.explore_state = 'front'

    def callback(self, msg):
        if self.start_time == 0:
            self.start_time = rospy.get_time()
            return

        if self.execute == False:
            return
        
        if self.explore_state == "explored":
            return


        last_sec = (rospy.get_time().to_sec() - self.max_gas_value_time.to_sec())
        if last_sec  > self.timeout_sec:
            rospy.logwarn_once("Robot discovered goal!")
            self.explore_state = "explored"
            self.cmd_x = 0.0
            self.cmd_yaw = 0.0
            self.goal_pose.header.seq = self.goal_pose.header.seq + 1
            self.goal_pose.header.stamp = rospy.Time.now()
            self.goal_pose.pose = self.final_robot_pose
            self.goal_pub.publish(self.goal_pose)
            return

        #front_dist = msg.ranges[0]
        front_dists = msg.ranges[:20]+ msg.ranges[340:]
        front_dist = min(list(map(lambda x: inf_distance if x == float('inf') else x, front_dists)))
        
        if self.before_gas_value < self.gas_value:
            self.explore_state = 'front'

        if (front_dist < territory_radius):
            self.cmd_x = 0.0
            self.cmd_yaw = 0.5
            self.explore_state = 'front'
            rospy.loginfo_throttle(1.0, 'state: avoiding obstacle',)
        else:
            self.cmd_yaw = 0.0
            self.cmd_x = 0.0
            rospy.loginfo_throttle(1.0, 'state: %s', self.explore_state)
            self.explore()

        cmd_msg = Twist()
        cmd_msg.linear.x = self.cmd_x
        cmd_msg.angular.z =self.cmd_yaw
        self.vel_pub.publish(cmd_msg)

if __name__ == "__main__":
    try:
        gas_scrutinize_action = gas_scrutinize()
    except rospy.ROSInterruptException: pass