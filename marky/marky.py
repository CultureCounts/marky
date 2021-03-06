#!/usr/bin/env python

import os, subprocess, re, sys, string, json, argparse, datetime, time, signal, tempfile
import types
from . import stats, mailer, args, ecd
#import speedup
from .config import config
from .debug import debug_msg, error_msg, warning_msg

# Codes used by the execute_and_capture_output methods.
TIMEOUT_ERROR = 1
FAILURE_ERROR = 2
FILTER_FAILED_ERROR = 3

# Function used to capture all output from a program it executes.
# Executes the whole program before returning any output.
def execute_and_capture_output(program):
	output = None
	try:
		output = subprocess.check_output(program, shell=True, stderr=subprocess.STDOUT)
	except subprocess.CalledProcessError as e:
		# TODO: Work out how on earth I get information about the error!
		raise Exception("Run failed!", FAILURE_ERROR)
	return str(output)

def execute_and_capture_output_with_timeout(program, timeout):
	try:
		output_file = tempfile.SpooledTemporaryFile()
		start = datetime.datetime.now()
		process = subprocess.Popen(program, shell=True, stdout=output_file, stderr=subprocess.STDOUT)
		while process.poll() is None:
			time.sleep(0.5)
			now = datetime.datetime.now()
			if (now - start).seconds > timeout:
				warning_msg("Timing out! (" + str((now-start).seconds) + "s)")
				os.kill(process.pid, signal.SIGKILL)
				os.waitpid(-1, os.WNOHANG)
				raise Exception("Run timed out!", TIMEOUT_ERROR)
		output_file.seek(0)
		raw = output_file.read()
		output_file.close()
		return str(raw)
	except subprocess.CalledProcessError as e:
		# TODO: Work out how on earth I get information about the error!
		raise Exception("Run failed!", FAILURE_ERROR)

# Implementation of pushd
directories = []
def enter_directory(directory):
	global directories
	directories.append(os.getcwd())
	try:
		os.chdir(directory)
	except Error:
		directories.pop()

# Implementation of popd
def leave_directory():
	global directories
	os.chdir(directories.pop())

# This program will run a filter (regular expression) on benchmark output,
# and will return the first value that was captured within parens.
def run_filter(raw, filter_function):
	match = re.search(filter_function, raw)
	if match:
		return match.group(1)
	else:
		warning_msg("Filter returned None! Filter was: " + filter_function.pattern)
		raise Exception("Filter failed!", FILTER_FAILED_ERROR)

# Should do similar to the above, but return a list of all matches
# that were between parens.
def run_multi_filter(raw, filter_function):
	pass

# Attempt to convert a string of data to the correct type.
def convert_data(s):
	n = s
	try:
		n = int(s)
		# s must've been an int!
	except ValueError:
		try:
			n = float(s)
			# s must've been a float!
		except ValueError:
			# s isn't a float or an int, assume it's a string.
			n = s
	return n

# For a run, converts all the data in it to the correct type.
def cleanup_run(run):
	for field in list(run.keys()):
		run[field] = convert_data(run[field])
	return run

def get_raw_filename(name, iteration):
	filename = name.replace(" ", "") 
	filename = filename.replace("/", "_") 
	filename = filename.replace(":", "_") 
	filename += "-i" + str(iteration+1)
	return filename

def check_raw_output_exists(name, iteration):
	if config["loadraw"]:
		filename = get_raw_filename(name, iteration)
		load_location = config["loadraw_dir"] + "/" + filename
		return os.path.exists(load_location)
	else:
		return False

def save_raw_output(name, iteration, raw):
	directory = config["saveraw_dir"]
	if not os.path.exists(directory):
		debug_msg(3, "Raw output directory doesn't exist! Creating...")
		os.mkdir(directory)

	filename = get_raw_filename(name, iteration)
	save_location = directory + "/" + filename
	f = open(save_location, "w")
	f.write(raw)
	f.close()

	debug_msg(3, "Saved raw output to " + save_location)

def load_raw_output(invocation, iteration):
	directory = config["loadraw_dir"]
	filename = get_raw_filename(invocation, iteration)
	load_location = directory + "/" + filename
	f = open(load_location, "r")
	raw = f.read()
	f.close()
	return raw
	
# This converts the provided results table to a string containing a CSV representation.
def convert_to_csv(results):
	# TODO: work out how to produce the headings
	s = '"experiment_name","benchmark","i",\n'
	for (exp_name, exp) in list(results["experiments"].items()):
		for (bm_name, bm) in list(exp["benchmarks"].items()):
			run_counter = 1
			for run in bm["runs"]:
				s += '"' + exp_name + '","' + bm_name + '",' + str(run_counter) + ',' 
				s += ','.join([str(v) for v in list(run.values())])
				s += "\n"
				run_counter += 1
			if "aggregates" in bm:
				for (agg_name, agg) in list(bm["aggregates"].items()):
					s += '"' + exp_name + '","' + bm_name + '","**' + agg_name + '**",' 
					s += ','.join([str(v) for v in list(agg.values())])
					s += "\n"

	return s

# TODO: implement this
def convert_to_widecsv(results):
	pass

# This method modifies one of the config files of the program being run.
# all instances of 'pattern' have been replaced by the given 'value'.
def update_based_on_file_argument(template_file, output_file, pattern, value):
	assert os.path.exists(template_file)
	assert os.path.exists(output_file)
	tf = open(template_file, "r")
	of = open(output_file, "w")
	modified = False
	for line in tf.readlines():
		newline = line.replace(pattern, str(value))
		if newline != line:
			of.write(newline)
			modified = True
		else:
			of.write(line)
	if not modified:
		error_msg('Template file "' + template_file + '" did not contain instance of pattern "' + pattern + '".')
	of.close()
	tf.close()

# TODO: Add caching here?
# This reads arguments for use when executing a benchmark from the given filename.
# This returned string is expected to replace the name of the benchmark, so should contain it!
def get_arguments_from_file(filename):
	assert os.path.exists(filename)
	f = open(filename, "r")
	args = f.read().strip()
	f.close()
	return args

def execute_post_function(post_function, post_function_arguments, name, iteration, timestamp):	
	actual_post_function_arguments = []
	for arg in post_function_arguments:
		
		# Awesome hack!!1
		if (arg == "GETUNIQUEFILENAME"):
			arg = "arcsimMemProfile-" + get_raw_filename(name, iteration) + ".csv"
		elif (arg == "GETTIMESTAMP"):
			arg = timestamp
		
		
		if (isinstance(arg, types.FunctionType)):
			actual_post_function_arguments.append(arg())
		else:
			actual_post_function_arguments.append(arg)
	
	post_function(*actual_post_function_arguments)
	
# -----
# Functions that should be exposed to main are below:
# -----

# This function is actually used to execute the experiments.
# It returns a currently-amorphous table of information about the experiments.
def run(suite):
	# The amorphous monstrosity of a table
	total_result_table = {}
	total_result_table["experiments"] = {}

	# Go through the programs...
	for (program_alias, program) in list(suite.programs.items()):

		# Check if there's argument variables that will require iterating over
		if ((len(suite.argument_variables) + len(suite.file_argument_variables)) == 0):

			exp_name = program_alias	

			# There were none, so simply run this program with no extra arguments
			debug_msg(1, "BEGIN EXPERIMENT: " + exp_name)
			total_result_table["experiments"][exp_name] = run_experiment(suite, program, program_alias, exp_name)

		else:
			# There are some, so use args.get_experiment_arguments to get a list of all combos, iterate over them.	
			for experiment_arguments in args.get_experiment_arguments(suite.argument_variables, suite.file_argument_variables):
				exp_params = ""
				experiment_arguments_string = ""
				for exp_arg in experiment_arguments:
					(name, value, is_file_arg_var) = exp_arg
					if is_file_arg_var:
						exp_params += (name + ":" + str(value) + " ")

						# change a config file
						(temp_file, output_file, pattern, values) = suite.file_argument_variables[name]
						update_based_on_file_argument(temp_file, output_file, pattern, value)

					else:
						exp_params += args.emit_argument(name, value)
						experiment_arguments_string += args.emit_argument(name, value)

				exp_name = program_alias + " " + exp_params
				debug_msg(1, "BEGIN EXPERIMENT: " + exp_name)
				total_result_table["experiments"][exp_name] = run_experiment(suite, program, program_alias, exp_name, experiment_arguments_string)


	return total_result_table

# An "experiment" is categorised as any program + the arguments we wish to use for that program.
def run_experiment(suite, program, program_alias, exp_name, experiment_arguments = ""): 

	experiment_table = {}
	experiment_table["benchmarks"] = {}

	# Convert the dict of benchmark groups, to a list of benchmark tuples called actual_benchmarks
	# We will then iterate over that.
	actual_benchmarks = []
	for (group_name, group_benchmarks) in list(suite.benchmarks.items()):
		for (name, directory, executescript, timeout) in group_benchmarks:
			actual_benchmarks.append((group_name, name, directory, executescript, timeout))

	# Go through the benchmarks...
	for (group_name, benchmark, directory, executescript, timeout) in actual_benchmarks:

		benchmark_name = group_name + " ++ " + benchmark

		enter_directory(directory)
		debug_msg(3, "Entered into " + os.getcwd())

		if (executescript):
			benchmark = get_arguments_from_file(executescript)

		# Construct the command used to execute the benchmark
		invocation = " ".join([suite.pre_arguments, program, suite.core_arguments, experiment_arguments, suite.benchmark_argument, benchmark])

		if config["should_warmup"]:
			debug_msg(1, "RUN: '" + invocation + "' (WARMUP)")
			try:
				if timeout:
					execute_and_capture_output_with_timeout(invocation, timeout)
				else:
					execute_and_capture_output(invocation)
			except Exception as e:
				if e.args[1] == TIMEOUT_ERROR:
					debug_msg(1, "Run timed out... (timeout is " + str(timeout) + "s)")
					timedout_iterations += 1
					failed_iterations += 1
				if e.args[1] == FAILURE_ERROR:
					debug_msg(1, "Run failed...")
					failed_iterations += 1

		# We store all the runs in here.
		run_table = []
		failed_iterations = 0
		timedout_iterations = 0

		# Go through the iterations...
		for i in range(suite.iterations):

			# This stores the fields collected for this run.
			run = {}

			debug_msg(1, "RUN: '" + invocation + "' (ITER: " + str(i+1) + "/" + str(suite.iterations) + ")")

			# string containing the raw output from the benchmark
			raw = ""
			try:
				raw_output_name = exp_name + experiment_arguments + benchmark

				start = datetime.datetime.now()
				
				timestamp = time.time() * 1000

				# Actually execute the benchmark
				if config["loadraw"] and check_raw_output_exists(raw_output_name, i):
					raw = load_raw_output(raw_output_name, i)
					debug_msg(1, "(loaded from file...)")
				elif timeout:
					raw = execute_and_capture_output_with_timeout(invocation, timeout)
				else:
					raw = execute_and_capture_output(invocation)

				end = datetime.datetime.now()

				# Save the output, if required
				if config["saveraw"]:
					save_raw_output(raw_output_name, i, raw)

				# Now collect the fields using our provided filters.
				for (field, field_filter) in list(suite.filters.items()):
					run[field] = run_filter(raw, field_filter)

				if not config["loadraw"]:
					delta = end - start
					runtime = float(delta.seconds)
					runtime += ( float((delta.microseconds)) / 1000000.0 )

					debug_msg(2, "Took " + str(runtime) + " seconds.")

					if config["should_time"] and not config["loadraw"]:
						run["marky runtime"] = str(runtime)

				# Collected data is all strings currently; convert to the correct types.
				run = cleanup_run(run)

				# Save this run
				run_table.append(run)

			except Exception as e:
				if len(e.args) < 2:
					raise e

				if e.args[1] == TIMEOUT_ERROR:
					debug_msg(1, "Run timed out... (timeout is " + str(timeout) + "s)")
					timedout_iterations += 1
					failed_iterations += 1
				if e.args[1] == FAILURE_ERROR:
					debug_msg(1, "Run failed...")
					failed_iterations += 1
				if e.args[1] == FILTER_FAILED_ERROR:
					debug_msg(1, "Filter failed...")
					failed_iterations += 1
					
		if ("post_function" in suite.__dict__ and "post_function_arguments" in suite.__dict__):
			execute_post_function(suite.post_function, suite.post_function_arguments, raw_output_name, i, timestamp)

		# Finished running this benchmark for X iterations...
		benchmark_result = {}
		benchmark_result["successes"] = len(run_table)
		benchmark_result["failures"] = failed_iterations
		benchmark_result["timeouts"] = timedout_iterations
		benchmark_result["attempts"] = len(run_table) + failed_iterations

		# Collect results from runs
		if len(run_table) > 0:
			benchmark_result["runs"] = run_table

		leave_directory()
		debug_msg(3, "Exited back to " + os.getcwd())

		# Save this benchmark in the benchmark table
		experiment_table["benchmarks"][benchmark_name] = benchmark_result
	
	return experiment_table

def print_results(results, formatter=json.dumps):
	print((formatter(results)))

def save_results(filename, results, formatter=json.dumps):
	f = open(filename, "w")
	f.write(formatter(results))
	f.close()

# Email the results!
email_results = mailer.send_email

formats = ["csv", "json", "widecsv"]
formatters = {"csv": convert_to_csv, "json": json.dumps, "widecsv": convert_to_widecsv}
default_print_format = "json"
default_save_format = "json"
default_email_format = "json"

#
# MAIN FUNCTION
#
def main():
	parser = argparse.ArgumentParser(
			description = "marky - a benchmark execution and statistics gathering framework")

	parser.add_argument('file', type=str, nargs=1, metavar='FILE', 
			help='A file containing an execution configuration. (or ECD) (Minus the .py)')
	parser.add_argument('--disable-aggregation', '-a', dest='disable_agg', action='store_true', 
			help='Turn off aggregation calculation for this session.')
	parser.add_argument('--warmup', '-w', dest='should_warmup', action='store_true', 
			help='Perform a warmup run of each benchmark that is not recorded.')
	parser.add_argument('--time', '-t', dest='should_time', action='store_true', 
			help='Use marky to measure the runtime of any experiments.')
	parser.add_argument('--explain', '-e', dest='should_explain', action='store_true', 
			help='Explain the experiments that will be run by the provided ECD.')
	parser.add_argument('--print', '-p', dest='should_print', action='store_true', 
			help='"Pretty-print" the results.')
	parser.add_argument('--print-format', '-pf', dest='printfmt', nargs=1, choices=formats, 
			help='Choose which format to print the data in. (default: json)')
	parser.add_argument('--load', '-l', dest='should_load', nargs=1, metavar='FILE', 
			help='Load previous results from a file. (supports JSON only)')
	parser.add_argument('--load-raw', '-lr', dest='should_loadraw', nargs=1, metavar='DIR', 
			help='Load the raw output from each run from the given directory.')
	parser.add_argument('--save', '-s', dest='should_save', nargs=1, metavar='FILE', 
			help='Output the results into a file.')
	parser.add_argument('--save-format', '-sf', dest='savefmt', nargs=1, choices=formats, 
			help='Choose which format to save the data in. (default: json)')
	parser.add_argument('--email', '-m', dest='should_email', nargs=1, metavar='ADDRESS', 
			help='Send an email to the address once complete. (Uses localhost unless --mailserver is given.)')
	parser.add_argument('--email-format', '-mf', dest='emailfmt', nargs=1, choices=formats, 
			help='Choose which format to email the data in. (default: json)')
	parser.add_argument('--mailserver', '-ms', dest='mailserver', nargs=1, metavar='HOST', 
			help='Use the provided host as a mailserver.')
	parser.add_argument('--save-raw', '-r', dest='should_saveraw', nargs=1, metavar='DIR', 
			help='Save the raw output from each run into the given directory.')
	parser.add_argument('--debug', '-d', dest='debuglevel', nargs=1, type=int, metavar='LEVEL', 
			help='Set debug info level. 1 = Announce each benchmark invocation. 2 = Include time taken. 3 = Everything else. (Default = 1) (Set to 0 for quiet, or use --quiet.)')
	parser.add_argument('--quiet', '-q', dest='quiet', action='store_true', 
			help='Hide all output (apart from errors.)')
	parser.add_argument('--speedups', '-cs', dest='should_calculate_speedups', action='store_true', 
			help='Assuming only two experiments will be run, calculate the speedups.')
	args = parser.parse_args()

	config["debuglevel"] = 2
	if args.debuglevel:
		config["debuglevel"] = args.debuglevel[0]
	if args.quiet:
		config["debuglevel"] = 0

	suite = None
	if args.file:
		# (ecd = Execution Configuration Description)
		ecd_name = args.file[0]
		ecd_name = ecd_name.replace(".py", "")
		suite = __import__(ecd_name)
		ecd.check_ecd(suite)

	if args.should_explain:
		ecd.explain_ecd(suite)
		exit(0)

	config["original_dir"] = os.getcwd()

	config["saveraw"] = False
	if args.should_saveraw:
		config["saveraw"] = True
		config["saveraw_dir"] = config["original_dir"] + "/" + args.should_saveraw[0]

	config["loadraw"] = False
	if args.should_loadraw:
		config["loadraw"] = True
		config["loadraw_dir"] = config["original_dir"] + "/" + args.should_loadraw[0]
		if not os.path.exists(config["loadraw_dir"]):
			error_msg("Raw results directory required for loading doesn't exist!")
		debug_msg(1, "Will load output from " + config["loadraw_dir"])

	config["should_warmup"] = False
	if args.should_warmup:
		config["should_warmup"] = True

	config["should_time"] = False
	if args.should_time:
		config["should_time"] = True

	results = None
	if args.should_load:
		debug_msg(1, "Loading previous results table from " + args.should_load[0])
		json_file = open(args.should_load[0], "r")
		results = json.load(json_file)
		json_file.close()
	else:
		debug_msg(1, "Running experiment to obtain results!")
		os.chdir(suite.benchmark_root)
		results = run(suite)
		os.chdir(config["original_dir"])

	results["description"] = ecd.convert_ecd_to_description(suite)

	if not args.disable_agg:
		stats.perform_aggregation(suite, results)	

	#if args.should_calculate_speedups:
	#	speedup.calculate(results)

	if args.should_print:
		formatter_name = default_print_format
		if args.printfmt:
			formatter_name = args.printfmt[0]
		formatter = formatters[formatter_name]
		print_results(results, formatter=formatter)

	if args.should_save:
		formatter_name = default_save_format
		if args.savefmt:
			formatter_name = args.savefmt[0]
		formatter = formatters[formatter_name]
		save_results(args.should_save[0], results, formatter=formatter)

	if args.should_email:
		mailserver = 'localhost'
		if args.mailserver:
			mailserver = args.mailserver[0]

		formatter_name = default_email_format
		if args.emailfmt:
			formatter_name = args.emailfmt[0]
		formatter = formatters[formatter_name]
		email_results(args.should_email[0], results, mailserver=mailserver, formatter=formatter)

if __name__ == "__main__":
	main()
