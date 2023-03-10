import rospy
import actionlib
from actionlib_msgs.msg import *
from geometry_msgs.msg import Pose, PoseWithCovarianceStamped, Point, Quaternion, Twist, PoseStamped
from move_base_msgs.msg import MoveBaseAction, MoveBaseGoal
from random import sample
from math import pow, sqrt



class NavTest():
    def __init__(self):
        rospy.init_node('nav_test', anonymous=True)
        
        rospy.on_shutdown(self.shutdown)
        
        # How long in seconds should the robot pause at each location?
        self.rest_time = rospy.get_param("~rest_time", 1)
        
        # Are we running in the fake simulator?
        self.fake_test = rospy.get_param("~fake_test", False)
        
        # Goal state return values
        goal_states = ['PENDING', 'ACTIVE', 'PREEMPTED', 
                       'SUCCEEDED', 'ABORTED', 'REJECTED',
                       'PREEMPTING', 'RECALLING', 'RECALLED',
                       'LOST']
        
        # Set up the goal locations. Poses are defined in the map frame.  
        # An easy way to find the pose coordinates is to point-and-click
        # Nav Goals in RViz when running in the simulator.
        # Pose coordinates are then displayed in the terminal
        # that was used to launch RViz.
        locations = dict()
        
        locations['point1'] = Pose(Point(1.353, 0.793, 0.000), Quaternion(0.000, 0.000, 0.9517, 0.3069))
        locations['point2'] = Pose(Point(0.329, 4.858, 0.000), Quaternion(0.000, 0.000, -0.670, 0.743))
        locations['point3'] = Pose(Point(-3.641, 3.844, 0.000), Quaternion(0.000, 0.000, 0.786, 0.618))
        locations['point4'] = Pose(Point(-2.809, -0.310, 0.000), Quaternion(0.000, 0.000, 0.733, 0.680))
        locations['point5'] = Pose(Point(-2.339, 0.113, 0.000), Quaternion(0.000, 0.000, 0.250, 0.968))

        # locations['living_room_2'] = Pose(Point(1.471, 1.007, 0.000), Quaternion(0.000, 0.000, 0.480, 0.877))
        # locations['dining_room_1'] = Pose(Point(-0.861, -0.019, 0.000), Quaternion(0.000, 0.000, 0.892, -0.451))
        
        # Publisher to manually control the robot (e.g. to stop it, queue_size=5)
        self.cmd_vel_pub = rospy.Publisher('cmd_vel', Twist, queue_size=5)
        
        # Subscribe to the move_base action server
        self.move_base = actionlib.SimpleActionClient("move_base", MoveBaseAction)
        
        rospy.loginfo("Waiting for move_base action server...")
        
        # Wait 60 seconds for the action server to become available
        self.move_base.wait_for_server(rospy.Duration(60))
        
        rospy.loginfo("Connected to move base server")
        
        # A variable to hold the initial pose of the robot to be set by 
        # the user in RViz
        initial_pose = PoseWithCovarianceStamped()
        
        # Variables to keep track of success rate, running time,
        # and distance traveled
        n_locations = len(locations)
        n_goals = 0
        n_successes = 0
        i = n_locations
        distance_traveled = 0
        start_time = rospy.Time.now()
        running_time = 0
        location = ""
        last_location = ""
        i=0
        last_i=i
        # Get the initial pose from the user
        rospy.loginfo("*** Click the 2D Pose Estimate button in RViz to set the robot's initial pose...")
        rospy.wait_for_message('initialpose', PoseWithCovarianceStamped)
        self.last_location = Pose()
        rospy.Subscriber('initialpose', PoseWithCovarianceStamped, self.update_initial_pose)
        
        # Make sure we have the initial pose
        while initial_pose.header.stamp == "":
            rospy.sleep(1)
            
        rospy.loginfo("Starting navigation test")
        
        # Begin the main loop and run through a sequence of locations
        while not rospy.is_shutdown():
            # If we've gone through the current sequence,
            # start with a new random sequence
            # if i == n_locations:
            #     i = 0
            #     sequence = sample(locations, n_locations)
            #     # Skip over first location if it is the same as
            #     # the last location
            #     if sequence[0] == last_location:
            #         i = 1
            
            sequence = list(locations.keys());
            if i>=len(sequence):
                break
            location=sequence[i]
            # Get the next location in the current sequence
            # Keep track of the distance traveled.
            # Use updated initial pose if available.
            if initial_pose.header.stamp == "":
                distance = sqrt(pow(locations[location].position.x - 
                                    locations[last_location].position.x, 2) +
                                pow(locations[location].position.y - 
                                    locations[last_location].position.y, 2))
            else:
                rospy.loginfo("Updating current pose.")
                distance = sqrt(pow(locations[location].position.x - 
                                    initial_pose.pose.pose.position.x, 2) +
                                pow(locations[location].position.y - 
                                    initial_pose.pose.pose.position.y, 2))
                initial_pose.header.stamp = ""
            
            # Store the last location for distance calculations
            last_location = location
            last_i=i
            # Increment the counters
            i += 1
            n_goals += 1
        
            # Set up the next goal location
            self.goal = MoveBaseGoal()
            self.goal.target_pose.pose = locations[location]
            self.goal.target_pose.header.frame_id = 'map'
            self.goal.target_pose.header.stamp = rospy.Time.now()
            
            # Let the user know where the robot is going next
            rospy.loginfo("Going to: " + str(location))
            
            # Start the robot toward the next location
            self.move_base.send_goal(self.goal)
            
            # Allow 5 minutes to get there
            finished_within_time = self.move_base.wait_for_result(rospy.Duration(300)) 
            
            # Check for success or failure
            if not finished_within_time:
                self.move_base.cancel_goal()
                rospy.loginfo("Timed out achieving goal")
            else:
                state = self.move_base.get_state()
                if state == GoalStatus.SUCCEEDED:
                    rospy.loginfo("Goal succeeded!")
                    n_successes += 1
                    distance_traveled += distance
                    rospy.loginfo("State:" + str(state))
                elif state == GoalStatus.ABORTED:
                    rospy.loginfo("Goal aborted")
                    i=last_i
                    n_goals=i
                else:
                  rospy.loginfo("Goal failed with error code: " + str(goal_states[state]))
            
            # How long have we been running?
            running_time = rospy.Time.now() - start_time
            running_time = running_time.secs / 60.0
            
            # Print a summary success/failure, distance traveled and time elapsed
            rospy.loginfo("Success so far: " + str(n_successes) + "/" + 
                          str(n_goals) + " = " + 
                          str(100 * n_successes/n_goals) + "%")
            rospy.loginfo("Running time: " + str(trunc(running_time, 1)) + 
                          " min Distance: " + str(trunc(distance_traveled, 1)) + " m")
            rospy.sleep(self.rest_time)
            
    def update_initial_pose(self, initial_pose):
        self.initial_pose = initial_pose

    def shutdown(self):
        global mode
        mode=1
        rospy.loginfo("Stopping the robot...")
        self.move_base.cancel_goal()
        rospy.sleep(2)
        self.cmd_vel_pub.publish(Twist())
        rospy.sleep(1)

      
def trunc(f, n):
    # Truncates/pads a float f to n decimal places without rounding
    slen = len('%.*f' % (n, f))
    return float(str(f)[:slen])

class park():   
    def __init__(self):
        rospy.init_node('park')
        global lastseq
        global currentseq
        global position
        global direction
        global distance
        distance=10
        direction=0
        lastseq = 0
        currentseq=0
        velocityx=0
        anglez=0
        self.pub=rospy.Publisher("/cmd_vel",Twist, queue_size=5)
        rospy.Subscriber("/aruco_single/pose", PoseStamped, self.positionchange, queue_size=1)

        rospy.on_shutdown(self.shutdown)
        rospy.loginfo("Starting parking")
        rate=rospy.Rate(20.0)
        arucofind=0
        while not rospy.is_shutdown():
            
            if distance > 0.4:
               arucofind=1 
               if currentseq!=lastseq:
                 lastseq=currentseq
                 if direction == 0:
                    velocityx=0.08
                    anglez=-0.1
                 elif direction == 1:
                    velocityx=0.08
                    anglez=0.3
                 else:
                    velocityx=0.1
                    anglez=0
                    
               else:
                    velocityx=0.08
                    anglez=0
            elif distance>0.1:
                arucofind=1
                if currentseq!=lastseq:
                 lastseq=currentseq
                 if direction == 0:
                    velocityx=0.05
                    anglez=-0.2
                 elif direction == 1:
                    velocityx=0.05
                    anglez=0.2
                 else:
                    velocityx=0.05
                    anglez=0
                elif arucofind:
                    velocityx=0
                    anglez=0                     
                else:
                    velocityx=0.05
                    anglez=0               
            else:
                velocityx=0
                anglez=0
                print(distance)
            vel_msg=Twist()
            vel_msg.linear.x=velocityx
            vel_msg.angular.z=anglez
            self.pub.publish(vel_msg)
            rospy.loginfo("parking")
            
            rate.sleep()

    def positionchange(self, msg):
        global direction
        global distance
        global currentseq 
        global position 

        currentseq = msg.header.seq
        position = msg.pose.position
        x=msg.pose.position.x
        rospy.loginfo("pose x"+str(x))
        if x>0.05:
            #right
            direction=0
        elif x<0:
            #left
            direction=1
        else:
            direction=2
        distance = msg.pose.position.z
        rospy.loginfo("distance"+str(distance))

    def shutdown(self):
        rospy.loginfo("Stopping the robot...")
        rospy.sleep(2)
        self.pub.publish(Twist())
        rospy.sleep(1)

if __name__ == '__main__':
    try:
        global mode 
        mode=0
        if not mode:
            NavTest()
        else:
            park()
        print("End init")       
        rospy.spin()
    except rospy.ROSInterruptException:
        rospy.loginfo("AMCL navigation test finished.")
