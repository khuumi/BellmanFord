
Daniel Maxson
DSM2157 


a. This assignment was a lot harder than I had planned so I ended up spending several days on the assignment. The graph should converge and poison reverse works.
I attempted to code LINKDOWN and LINKUP and CLOSE but currently they are only partially functioning. 

Transfer is working completely as expected where both chunks will get concacted together and outputted to OUTPUT( currently set as "output.jpg"). 

b. My developement enviroment was Sublime Text on a Mac and then a transfer of files over to CLIC using Cyberduck. All code works on ClIC. 

c. Run the program the following way on each client with an appropiate config file:

./bfclient.py config-file.txt

I used six different config files and ran them each on a port 20000-20006. The config files are included. To test using them, please comment out line 642.


It is important that all nodes are loaded up quickly otherwise there will be a link_down message sent. 

d. The two most important commands in my code are: 

SHOWRT: Displays the converged graphs route

TRANSFER <IP> <PORT> : Transfers the packet set in the config file.

I hope you have a great summer, and thanks for grading my work!
