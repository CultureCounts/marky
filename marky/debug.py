from .config import config

def debug_msg(level, msg):
	if config["debuglevel"] >= level:
		spacer = "  " * (level-1)
		print((spacer + "[D" + str(level) + "] " + msg))

def warning_msg(msg):
	if config["debuglevel"] > 0:
		print(("[WARNING] " + msg))

def error_msg(msg):
	print(("[ERROR] " + msg))
	print("Quitting...")
	exit(1)

def seen_warnings():
	pass

def reset_warnings():
	pass
