import select
import socket
import Queue
import sys

import logging

'''
    a custom logging module 
    with specified formmat
    support file and stream output
'''
class MCRLogger(object):

    def __init__(self,logfilename=None,logLevel="INFO",loggerName="root"):
        
        self._logger = logging.getLogger(loggerName)#init logger
        '''
            set logger level 
            CRITICAL50 ERROR40 WARNING30 INFO20 DEBUG10 NOTSET0
            the logger only print the log msg above or equal the level's value
        '''
      
        if logLevel.upper() == "DEBUG":
            self._logger.setLevel(logging.DEBUG)
        elif logLevel.upper() == "WARNING":
            self._logger.setLevel(logging.WARNING)
        elif logLevel.upper() == "ERROR":
            self._logger.setLevel(logging.ERROR)
        elif logLevel.upper() == "INFO":
            self._logger.setLevel(logging.INFO)
        elif logLevel.upper() == "CRITICAL":
            self._logger.setLevel(logging.CRITICAL)
        else:
            self._logger.setLevel(logging.NOTSET)
            
        formatter = logging.Formatter(
        '%(asctime)s %(name)-12s %(levelname)-8s %(message)s')#set logger formatter
        #eg 2016-05-19 20:27:45,612 root         INFO     info message
        '''
            set logger handler 
            there is no file output by default,if set the msg will be added 
            in the setted file according the formmater
        '''
        if logfilename:
            self._fileHanlder = logging.FileHandler(logfilename,mode='a')
            self._fileHanlder.setFormatter(formatter)
            self._logger.addHandler(self._fileHanlder)
        else:
            self._streamHandler=logging.StreamHandler()
            self._streamHandler.setFormatter(formatter)
            self._logger.addHandler(self._streamHandler)

class MultiConnectionRepeater(object):
    def __init__(self,
                 localhost,
                 localport,
                 remotehost,
                 remoteport,
                 logFile="MCR.log",
                 logLevel="ERROR",
                 loggerName="MCR",
                 listen_num=10):

        self._localhost = localhost
        self._remotehost= remotehost
        self._localport = localport
        self._remoteport = remoteport
        self._logger = MCRLogger(logFile,logLevel,loggerName=loggerName)._logger
        #create a socket
        self._server = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        self._server.setblocking(False)
        #set option reused
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR  , 1)
 
        self._server_address= (self._localhost,int(self._localport))
        self._server.bind(self._server_address)
 
        self._server.listen(listen_num)

        self._client_address_ =(self._remotehost,int(self._remoteport))

        #sockets from which we except to read
        self._inputs = [self._server]
 
        #Outgoing message queues (socket:Queue)
        self._message_queues = {}
        self._client_msg_queues = {}

    def clean_socket(self,s=None):

        if s:
            self._inputs.remove(s)
            #Remove message queue
            if s in self._message_queues.keys():

                del self._message_queues[s][1]
                self._inputs.remove(self._message_queues[s][0])
                self._message_queues[s][0].close()
                
            elif s  in self._client_msg_queues:
                del self._client_msg_queues[s][1]
                self._inputs.remove(self._client_msg_queues[s][0])
                self._client_msg_queues[s][0].close()
            else:
                pass
            s.close()





    #def get_lan_ip(self):
    #    ip = socket.gethostbyname(socket.gethostname())
    #    if ip.startswith("127.") and os.name != "nt":
    #        interfaces = ["eth0","eth1","eth2","wlan0","wlan1","wifi0","ath0","ath1","ppp0"]
    #        for ifname in interfaces:
    #            try:
    #                ip = get_interface_ip(ifname)
    #                break;
    #            except IOError:
    #                pass
    #    return ip
        
    def forward(self):
        while self._inputs:
            self._logger.info("waiting for next event")
            #print "waiting for next event"
            readable , writable , exceptional = select.select(self._inputs, [],[])
 
            # When timeout reached , select return three empty lists
            if not (readable or writable or exceptional) :
                self._logger.error("Time out ! ")
                break;    
            for s in readable :
                if s is self._server:
                    # A "readable" socket is ready to accept a connection
                    connection, client_address = s.accept()
                    self._logger.info( "    connection from "+str(client_address))
                    connection.setblocking(0)
                    self._inputs.append(connection)

                    #establish a unique socket to port forward data
                    try:
                        client_connection = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
                        #client.setblocking(False)
                        client_connection.connect(self._client_address_)
                
                    except Exception as e:
                        #print e
                        self._logger.error("create remote socket err "+str(e))
                        client_connection.close()
               
                    else:
                        self._inputs.append(client_connection)

                        #message_queues.setdefault(connection,client_connection)
                        self._message_queues.setdefault(connection,[]).append(client_connection)
                        self._message_queues.setdefault(connection,[]).append(Queue.Queue())

                        #client_msg_queues.setdefault(client_connection,connection)
                        self._client_msg_queues.setdefault(client_connection,[]).append(connection)
                        self._client_msg_queues.setdefault(client_connection,[]).append(connection)
                 

                    #message_queues[connection] = Queue.Queue()

                else:
                    try:
                        data = s.recv(1024)
                    except Exception as e:
                        #print e
                        self._logger.error("receive data from "+str(s.getpeername())+" error "+str(e))
                        self.clean_socket(s)                       
                        pass
                    except socket.gaierror, e:
                        if e.errno == 10054:
                            self.clean_socket(s)
                    else:
                        if data :
                            #print " received " , data , "from ",s.getpeername()    
                            self._logger.info(" received "+data+" from "+str(s.getpeername()))
                            if s in self._message_queues.keys():
                                try:
                                    self._message_queues[s][0].send(data)
                                except Exception as e:
                                    #print e
                                    self._logger.error("repeater send data error "+str(e))
                                    self.clean_socket(s)

                            elif s in self._client_msg_queues.keys():
                                try:
                                    self._client_msg_queues[s][0].send(data)
                                    
                                except Exception as e:
                                    #print e
                                    self._logger.error("repeater send back data error"+str(e))
                                    self.clean_socket(s)
                            # Add output channel for response    
             
                        else:
                            #Interpret empty result as closed connection
                                
                            self._logger.debug("  closing "+ str(client_address))
                            self.clean_socket(s)
                    
    
     
            for s in exceptional:
                self._logger.error(" exception condition on "+ str(s.getpeername()))
                #stop listening for input on the connection
                self.clean_socket(s)


if __name__=="__main__":

    #mcr = MultiConnectionRepeater(localhost="192.168.11.10",localport="10001",remotehost="192.168.11.8",remoteport="80")
    #mcr.forward()
    if len(sys.argv)<5:
        print "Usage:<localIP> <localPort> <remoteIP> <remotePort>"
        sys.exit(0)
    else:
        mcr = MultiConnectionRepeater(localhost=sys.argv[1],localport=sys.argv[2],remotehost=sys.argv[3],remoteport=sys.argv[4])
        mcr.forward()
