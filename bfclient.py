import sys, socket, select, json, os, signal, base64, datetime
from threading import Timer
from thread import *

UDP_IP = "127.0.0.1"
SELF_IP = ""
OUTPUT = "output.jpg"

TIMEOUT = 0
LOCALPORT = 0
file_chunk_to_transfer = ""
file_seq_number = 0

#List of UDP Write only sockets [Need to loop through these to send ]
list_sockets = []

dict_file_parts = {}
dict_temp_file_parts = {}

#List of route objects
routing_table = {}
neighbors = {}

def print_with_prompt(to_print=""):
	if len(to_print) > 1:
		print to_print
	sys.stdout.write('%> ')	
	sys.stdout.flush()


#Repeatable Timer by MestreLion(stackoverflow)

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False

    def reset(self):
    	self.stop()
    	self.start()

    def running(self):
    	return self.is_running

#Object for Node 
class Node(object):
	"""Class for the graph nodes, used in the routing table"""
	def __init__(self, ip="127.0.0.1", port=5000, weight=0.0, 
				next_hop_ip="-1", next_hop_port=-1, original_weight=-1): 
		self.ip = ip
		self.port = port
		self.weight = weight
		self.next_hop_ip = next_hop_ip
		self.next_hop_port = next_hop_port
		self.timer = RepeatedTimer(3*TIMEOUT, link_down, self.ip, self.port)
		self.old_w = original_weight

		#If this hasn't sent a table in 3*TIMEOUT seconds than we should 
		#call link down for this node 

def close_client(signum, frame):
 	"""Sets a nodes distance to infinity -- route messages won't be sent anymore"""
 	os._exit(1)

def read_file(file_name):
	global LOCALPORT
	global TIMEOUT
	global file_chunk_to_transfer
	global file_seq_number
	global routing_table
	global SELF_IP

	config = open(file_name, 'r')

	first_line = config.readline().split(' ')

	LOCALPORT = int(first_line[0])
	TIMEOUT = int(first_line[1])
	SELF_IP = "{0}:{1}".format(UDP_IP, LOCALPORT)

	if len(first_line) > 2:
		file_chunk_to_transfer = first_line[2]

	if len(first_line) > 3:
		file_seq_number = int(first_line[3].rstrip('\n'))

	for line in config:
		ip_addr = line.split(' ')[0].split(":")[0]
		port = int(line.split(' ')[0].split(":")[1])
		weight = float(line.split(' ')[1].rstrip('\n'))

		ip_addr_port = "{0}:{1}".format(ip_addr, port)
		routing_table[ip_addr_port] = Node(ip_addr, port, weight, ip_addr, port, weight)
		neighbors[ip_addr_port] = (ip_addr, port)

		routing_table[ip_addr_port].timer.start()


def reset_timer(packet):
	"""Reset each nodes timer each time a routing table is recieved from them"""
	origin_packet = json.loads(packet)
	try:
		ip_addr, port = origin_packet["origin_addr"]
	except:
		# print "exception occured for some reason"
		# print origin_packet
		return

	ip_addr_port = "{0}:{1}".format(ip_addr, port)

	if ip_addr_port in neighbors:
		if routing_table[ip_addr_port].weight != float("inf"):
			try:
				routing_table[ip_addr_port].timer.reset()
			except KeyError:
				print "{0} doesn't exist".format(ip_addr_port)
				print_with_prompt()



def reset_table():

	for ip_addr_port in routing_table:

		#If the node is not down and is a direct neighbor send distance vector
		if ip_addr_port in neighbors:
			if routing_table[ip_addr_port].weight != float("inf"):
				routing_table[ip_addr_port].weight = routing_table[ip_addr_port].old_w
		else:
			routing_table[ip_addr_port].weight = float("inf")
			routing_table[ip_addr_port].next_hop_port = -1
			routing_table[ip_addr_port].next_hop_ip = ""

	send_route_update()


def update_table(new_table, src_addr):
	"""Updates a new routing table with all newly discovered nodes on new_table from
		ip and port src_addr"""
	global routing_table
	src_addr_port = "{0}:{1}".format(src_addr[0], src_addr[1])

	try:
		weight_to_node = routing_table[src_addr_port].weight
	except KeyError:
			return
	
	self_ip_port = "{0}:{1}".format(UDP_IP, LOCALPORT)


	#Loop through the new node tuples that were on this udp-received table
	for ip_addr_port, node_tuple in new_table.iteritems():
		#Skip self 
		if ip_addr_port == self_ip_port:
			continue
		#Skip the dictionary's header
		if ip_addr_port == "header":
			continue
		if not ":" in ip_addr_port:
			continue


		#Add the current weight to the weight for each node
		new_weight = float(node_tuple[2]) + weight_to_node

		# print "node_tuple is {0}".format(node_tuple)
		#If it is a new node
		if ip_addr_port not in routing_table:
			new_node = Node(node_tuple[0], node_tuple[1])
			new_node.weight = new_weight
			new_node.next_hop_ip = src_addr[0]
			new_node.next_hop_port = src_addr[1] 
			routing_table[ip_addr_port] = new_node
			# print "table was updated --added"
			send_route_update()

		#DEBUG

		# if ip_addr_port == "127.0.0.1:20005" and self_ip_port == "127.0.0.1:20000" \
		# and routing_table[ip_addr_port].next_hop_port == -1:
		# 	print "Weight is: {0}".format(new_weight)
		# 	print "The culprit is {0}".format(src_addr_port)


		#If it is not a new node but it has a weight less than what we had before
		elif new_weight < routing_table[ip_addr_port].weight:
			routing_table[ip_addr_port].weight = new_weight
			routing_table[ip_addr_port].next_hop_ip = src_addr[0]
			routing_table[ip_addr_port].next_hop_port = src_addr[1]
			# print "table was updated -- closer"

			send_route_update() # Send a route-update each time that the routing table
								# is changed. 

def send_route_update():
	"""Sends a jsonified stripped-down version of the routing tables just to this
		nodes current neighbors"""

	origin_addr = (UDP_IP, LOCALPORT)
	

	# print "send_route_update was called "
	# print TIMEOUT 
	for client in routing_table.itervalues():

		distance_vector = {}
		#To distinguish from the other types of messages
		distance_vector["header"] = "route_update"
		distance_vector["origin_addr"] = origin_addr

		# print distance_vector["origin"]
		# print "just printed"

		#If any of the links will go through this node set their weight to infinity
		#This is our poison reverse implementation
		for ip_addr_port, node in routing_table.items():
			if node.next_hop_ip == client.ip and node.next_hop_port == client.port:
				distance_vector[ip_addr_port] = (node.ip, node.port, float("inf"))
			else:
				distance_vector[ip_addr_port] = (node.ip, node.port, node.weight)

		json_dist_vector = json.dumps(distance_vector)

		#If the node is not down and is a direct neighbor send distance vector
		if client.next_hop_ip == client.ip and client.next_hop_port == client.port:
			if client.weight != float("inf"):
				sock.sendto(json_dist_vector, (client.ip, int(client.port)))

def show_route():
	"""Prints the route to standard out"""
	for node in routing_table.itervalues():
		# print node
		print "Destination = {0}:{1}, Cost = {2}, Link = ({3}:{4})" \
		.format(node.ip, node.port, node.weight, node.next_hop_ip, 
					node.next_hop_port)
	print_with_prompt()

def recv_link_down(packet, src_addr):
	global routing_table
	"""Gets called when a link down command is received... sets weight to infinity"""
	src_addr_port = "{0}:{1}".format(src_addr[0], src_addr[1])

	origin = (UDP_IP, LOCALPORT)

	# routing_table[src_addr_port].weight = float("inf")

	#Set the weight of anything whose next_hop went through there to infinity
	#Including the actual node 
	for node in routing_table.itervalues():
		if node.next_hop_ip == src_addr[0] and node.next_hop_port == src_addr[1]:
			node.weight = float("inf") 

	routing_table[src_addr_port].timer.stop()


	# print "just stopped timer for {0}".format(src_addr_port)
	# if routing_table[src_addr_port].timer.running():
	# 	print "timer is still running LOL also..."

	reset_table()
	for neighbor_node in neighbors.itervalues():
			packet = {}
			packet["header"] = "reset_table"
			packet["origin_addr"] = origin
			sock.sendto(json.dumps(packet), (neighbor_node[0], neighbor_node[1]))

	send_route_update()


def link_down(ip_addr, port):
	"""Puts a links weight to infinity and cancels the timer"""

	origin = (UDP_IP, LOCALPORT)
	global routing_table
	message_dict = {}
	message_dict["header"] = "link_down"
	message_dict["origin_addr"] = origin


	ip_addr_port = "{0}:{1}".format(ip_addr, port)

	# if routing_table[ip_addr_port].timer.running():
	# 	print "Link down because my timer is still running"

	next_hop_ip = routing_table[ip_addr_port].next_hop_ip
	next_hop_port = routing_table[ip_addr_port].next_hop_port
	weight = routing_table[ip_addr_port].weight

	if weight == float("inf"):
		print_with_prompt("Link for {0} was already stopped before".format(ip_addr_port))
		return

	#We only can do a link_down on our direct neighbors 
	if ip_addr_port in neighbors:
		#Send a message to the node saying our relationship is broken
		sock.sendto(json.dumps(message_dict), (ip_addr, int(port)))

		#Then update our routing table
		routing_table[ip_addr_port].weight = float("inf")

		for node in routing_table.itervalues():
			if node.next_hop_ip == ip_addr and node.next_hop_port == port:
				node.weight = float("inf") 
		print_with_prompt("Link for {0} was taken down".format(ip_addr_port))
		routing_table[ip_addr_port].timer.stop()


		#Tell all my neighbors that they need to reset their tables also
		for neighbor_node in neighbors.itervalues():
			packet = {}
			packet["origin_addr"] = origin

			packet["header"] = "reset_table"
			sock.sendto(json.dumps(packet), (neighbor_node[0], neighbor_node[1]))


		reset_table()
		send_route_update()

	else: 
		print_with_prompt("Sorry {0}:{1} not your neighbor -- we coudln't take it down" \
			.format(ip_addr, port)) \
		

def recv_link_up(packet, src_addr):
	"""Gets called when a link up command is received... sets weight to new weight"""
	src_addr_port = "{0}:{1}".format(src_addr[0], src_addr[1])
	routing_table[src_addr_port].weight = packet["weight"]
	routing_table[src_addr_port].timer.start()
	origin = (UDP_IP, LOCALPORT)


	#Tell all my neighbors that they need to reset their tables also
	for neighbor_node in neighbors.itervalues():
		packet = {}
		packet["origin_addr"] = origin

		packet["header"] = "reset_table"
		sock.sendto(json.dumps(packet), (neighbor_node[0], neighbor_node[1]))


		reset_table()

	send_route_update()


def link_up(ip_addr, port, weight):
	"""Reinstates a previously link-downed neighbor to a weight specified"""
	ip_addr_port = "{0}:{1}".format(ip_addr, port)
	origin = (UDP_IP, LOCALPORT)


	message_dict = {}
	message_dict["header"] = "link_up"
	message_dict["weight"] = weight

	next_hop_ip = routing_table[ip_addr_port].next_hop_ip
	next_hop_port = routing_table[ip_addr_port].next_hop_port
	prev_weight = routing_table[ip_addr_port].weight

	# print prev_weight

	if prev_weight != float("inf") and ip_addr_port not in neighbors:
		print_with_prompt("Link for {0} wasn't down ".format(ip_addr_port))
		return

	#We only can do a link up on our direct neighbors 
	if ip_addr_port in neighbors:
		sock.sendto(json.dumps(message_dict), (ip_addr, int(port)))

		routing_table[ip_addr_port].weight = weight
		routing_table[ip_addr_port].timer.start()
		print_with_prompt("Link for {0} was put up with {1} weight" \
						.format(ip_addr_port, weight))


		#Tell all my neighbors that they need to reset their tables also
		for neighbor_node in neighbors.itervalues():
			packet = {}
			packet["header"] = "reset_table"
			packet["origin_addr"] = origin

			sock.sendto(json.dumps(packet), (neighbor_node[0], neighbor_node[1]))

		reset_table()

		send_route_update()


	else: 
		print_with_prompt("Sorry thats not your neighbor -- we coudln't link it up")

def concat_files():
	global dict_file_parts

	data1 = dict_file_parts[1]
	data2 =  dict_file_parts[2]

	f = open(OUTPUT, "wb")
	f.write(data1)
	f.write(data2)
	f.close()

	dict_file_parts = {}


def recv_transfer(packet, rcv_addr):
	ip_addr_port = "{0}:{1}".format(packet["dest_ip"], packet["dest_port"])

	print "TRANSFER: File chunk # {0} arrived at destination.".format(packet["file_seq_number"])
	print "Time: {0}".format(datetime.datetime.now())
	print packet["path"]
	print_with_prompt()	

	raw_data = packet["data"].decode('base64')

	global dict_file_parts
	global dict_temp_file_parts

	#If the packet has arrived at final destination
	if int(packet["dest_port"]) == LOCALPORT and packet["dest_ip"] == "127.0.0.1":
	#if int(packet["dest_port"]) == LOCALPORT and packet["dest_ip"] == UDP_IP:
		#if it is the second out of two packets
		if len(dict_file_parts) == 0:
			file_seq_number = packet["file_seq_number"]
			dict_file_parts[file_seq_number] = raw_data

		elif len(dict_file_parts) == 1:
			file_seq_number = packet["file_seq_number"]
			dict_file_parts[file_seq_number] = raw_data

			concat_files()

		elif len(dict_file_parts) == 2:
			concat_files()
	else:
		next_hop_ip = routing_table[ip_addr_port].next_hop_ip
		next_hop_port = routing_table[ip_addr_port].next_hop_port

		print "File transfer is on its way..."
		print "Next destination is {0}:{1}".format(next_hop_ip, next_hop_port)

		print_with_prompt()


		packet["path"] = packet["path"] + "\n -> {0}:{1}".format(next_hop_ip, 
																next_hop_port)

		data = json.dumps(packet)

		sock.sendto(data, (next_hop_ip, next_hop_port))


def transfer(dest_ip, dest_port):
	ip_addr_port = "{0}:{1}".format(dest_ip, dest_port)
	origin = (UDP_IP, LOCALPORT)

	next_hop_ip = routing_table[ip_addr_port].next_hop_ip
	next_hop_port = routing_table[ip_addr_port].next_hop_port

	print "File transfer is on its way..."
	print "Next destination is {0}:{1}".format(next_hop_ip, next_hop_port)

	packet = {}
	packet["header"] = "transfer"
	packet["file_seq_number"] = file_seq_number
	packet["dest_port"] = dest_port
	packet["dest_ip"] = dest_ip
	packet["origin_addr"] = origin 


	data = ''
	with open(file_chunk_to_transfer, 'rb') as f:
		data = base64.b64encode(f.read())

	packet["data"] = data

	packet["path"] = "{0}:{1}\n -> {2}:{3}".format(UDP_IP, LOCALPORT, 
										next_hop_ip, next_hop_port)

	f.close()

	sock.sendto(json.dumps(packet), (next_hop_ip, next_hop_port))

	print_with_prompt()
def close():
	if raw_input("Do you really want to exit? Type y for yes")[:1] == "y":
		sys.exit()

def menu():

	print_with_prompt()
	while 1:
		command = raw_input("")

		if command[:6] == "SHOWRT":
			show_route()
		elif command[:8] == "LINKDOWN":
			if len(command.split(" ")) != 3:
				continue
			ip_addr = command.split(" ")[1]
			port = command.split(" ")[2]
			try:
				link_down(ip_addr, port)
			except KeyError:
				print "That IP doesn't exist"
				print_with_prompt()

		elif command[:6] ==  "LINKUP":
			if len(command.split(" ")) != 4:
				continue
			ip_addr = command.split(" ")[1]
			port = command.split(" ")[2]
			weight = command.split(" ")[3]

			try:
				link_up(ip_addr, port, weight)
			except KeyError:
				print "That IP doesn't exist"
				print_with_prompt()
		elif command[:5] == "CLOSE":
			close()
		elif command[:8] == "TRANSFER":
			if len(command.split(" ")) != 3:
				continue
			ip_addr = command.split(" ")[1]
			port = command.split(" ")[2]

			transfer(ip_addr, port)
		else:
			print "That command was invalid"
			print_with_prompt()

def main():
	global sock 

	if(len(sys.argv) != 2):
		print "Sorry, you need to have a decent config-file for me \
				 to work with"
		sys.exit()

	#Comment this out if you want it to work on 127.0.0.1
	global UDP_IP
	UDP_IP = socket.gethostbyname(socket.gethostname())

	config_file = sys.argv[1]
	read_file(config_file)
	# show_route()
	start_new_thread(menu, ())

	sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	sock.bind(("", LOCALPORT))
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576) 
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576) 

	#Timer to send route updates every TIMEOUT seconds
	t = RepeatedTimer(TIMEOUT, send_route_update)
	t.start()

	send_route_update()

	while 1:
		input_ready, output_ready, except_ready = select.select([sock], [], [])
		for s in input_ready:
			data, addr = s.recvfrom(65536)
			reset_timer(data)
			# print "received message:", data
			# try: 
			packet = json.loads(data)

			if packet["header"] == "route_update":
				update_table(packet, addr)
			elif packet["header"] == "link_down":
				recv_link_down(packet, addr)
			elif packet["header"] == "link_up":
				recv_link_up(packet, addr)
			elif packet["header"] == "reset_table":
				reset_table()
			elif packet["header"] == "transfer":
				recv_transfer(packet, addr)
			else:
				pass

			
signal.signal(signal.SIGINT, close_client)
if __name__ == "__main__": main()