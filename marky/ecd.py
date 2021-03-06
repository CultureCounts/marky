from . import debug

rules = [ \
("programs", dict, True), \
("benchmarks", dict, False), \
("argument_variables", dict, False), \
("file_argument_variables", dict, False), \
("core_arguments", str, False), \
("benchmark_argument", str, False), \
("iterations", int, False), \
("filters", dict, False), \
("filter_order", list, False), \
("benchmark_aggregates", dict, False), \
("experiment_aggregates", list, False), \
]

def explain_ecd(suite):
	print("marky - Experiments Explanation")
	print("-------------------------------")
	print()
	print("Marky will run the following programs:")
	for (program_alias, location) in list(suite.programs.items()):
		print(("  " + program_alias + " - found at " + location))
	print()
	print("... with the following benchmarks:")
	for (bm_group_name, bm_group) in list(suite.benchmarks.items()):
		print(("  (benchmark group: " + bm_group_name + ")"))
		for (bm_name, bm_loc, executescript, timeout) in bm_group:
			extra = ""
			if executescript:
				extra = " with execute script '" + executescript + "'"
			if timeout:
				extra += " - with timeout: " + str(timeout)
			print(("   " + bm_name + " - found in " + bm_loc + extra))
	print()
	print("... changing the following variables:")
	for (name, values) in list(suite.argument_variables.items()):
		print(("  '" + name + "' with values: " + str(values)))
	for (name, (t,output_file,p,values)) in list(suite.file_argument_variables.items()):
		print(("  '" + name + "' with values: " + str(values) + " (in config file " + output_file + ")"))
	print()
	print(("... running each benchmark " + str(suite.iterations) + " times."))
	print()
	print(("... with the core arguments '" + str(suite.core_arguments) + "'"))
	print()
	print("... running the following filters:")
	for (filter_name, f) in list(suite.filters.items()):
		print(("  " + filter_name))
	print()
	print("... using the following benchmark aggregates:")
	for (aggregate_name, a) in list(suite.benchmark_aggregates.items()):
		extra = ""
		if (aggregate_name in suite.experiment_aggregates):
			extra = " (*** experiment aggregate ***)"
		print(("  " + aggregate_name + extra))

def check_ecd(suite):
	debug.debug_msg(3, "Sanity checking the provided ECD...")
	visible_vars = list(suite.__dict__.keys())

	for (var_name, t, cannot_be_empty) in rules:
		if var_name not in visible_vars:
			debug.warning_msg("'" + var_name + "' variable must be present!")
		else:
			var = suite.__dict__[var_name]
			if type(var) is not t:
				debug.warning_msg("'" + var_name + "' must be of type: " + str(t))
			if cannot_be_empty and len(var) == 0:
				debug.warning_msg("'" + var_name + "' cannot be empty!")
		
	if debug.seen_warnings():
		debug.error_msg("Execution Configuration Description was invalid!")
		debug.reset_warnings()

def convert_ecd_to_description(suite):
	description = {}

	description["programs"] = suite.programs
	description["benchmarks"] = suite.benchmarks
	description["argument variables"] = suite.argument_variables
	description["file argument variables"] = suite.file_argument_variables
	description["iterations"] = suite.iterations
	description["core arguments"] = suite.core_arguments
	description["filters"] = []
	for (filter_name, f) in list(suite.filters.items()):
		description["filters"].append((filter_name, f.pattern))
	description["aggregates"] = [] 

	for (aggregate_name, a) in list(suite.benchmark_aggregates.items()):
		extra = ""
		if (aggregate_name in suite.experiment_aggregates):
			extra = " (*** experiment aggregate ***)"
		description["aggregates"].append(aggregate_name + extra) 

	return description	
