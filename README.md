Bellman Ford Simulation
==============

This python program is a simulation of the [Bellman Ford](http://en.wikipedia.org/wiki/Bellman%E2%80%93Ford_algorithm "Bellman Ford Algorithm") algorithm. Most code is fully functional except for the LINKDOWN, LINKUP, and CLOSE commands which only are have partial functionality. 

Run the program the following way on each client with an appropiate config file:

./bfclient.py config-file.txt

I used six different config files and ran them each on a port 20000-20006. The config files are included. To test using them, please comment out line 562.

It is also important that all nodes are loaded up quickly to prevent an automatic link_down message to be sent.  
