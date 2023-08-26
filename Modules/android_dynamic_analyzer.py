#!/usr/bin/python3

import os
import re
import sys
import time
import json
import threading
import subprocess

try:
    import pyaxmlparser
except:
    print("Error: >pyaxmlparser< module not found.")
    sys.exit(1)

try:
    import frida
except:
    print("Error: >frida< module not found.")
    sys.exit(1)

try:
    from rich import print
    from rich.progress import track
    from rich.table import Table
except:
    print("Error: >rich< module not found.")
    sys.exit(1)

# Legends
errorS = f"[bold cyan][[bold red]![bold cyan]][white]"
infoS = f"[bold cyan][[bold red]*[bold cyan]][white]"

# Gathering Qu1cksc0pe path variable
sc0pe_path = open(".path_handler", "r").read()

# Using helper library
if os.path.exists("/usr/lib/python3/dist-packages/sc0pe_helper.py"):
    from sc0pe_helper import Sc0peHelper
    sc0pehelper = Sc0peHelper(sc0pe_path)
else:
    print(f"{errorS} [bold green]sc0pe_helper[white] library not installed. You need to execute [bold green]setup.sh[white] script!")
    sys.exit(1)

# Disabling pyaxmlparser's logs
pyaxmlparser.core.log.disabled = True

# Configurating strings parameter
if sys.platform == "darwin":
    strings_param = "-a"
else:
    strings_param = "--all"

# Initialize a dictionary to store the current state of the folders
previous_states = {
    "/files": {
        "contents": [],
        "changes": 0
    },
    "/shared_prefs": {
        "contents": [],
        "changes": 0
    },
    "/app_DynamicOptDex": {
        "contents": [],
        "changes": 0
    }
}

class AndroidDynamicAnalyzer:
    def __init__(self, target_file):
        self.target_file = target_file
        self.PERMS = "rw-"
        self.MAX_SIZE = 20971520
        self.url_regex = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        self.ip_addr_regex = r"^((25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])$"
        self.frida_script = open(f"{sc0pe_path}/Systems/Android/FridaScripts/sc0pe_android_enumeration.js", "r").read()
        try:
            self.axmlobj = pyaxmlparser.APK(self.target_file)
        except:
            self.axmlobj = None

    def search_package_name(self, package_name):
        print(f"{infoS} Searching for existing installation...")
        exist_install = subprocess.check_output("adb shell pm list packages", shell=True).decode().split("\n")
        matchh = re.findall(rf"{package_name}", str(exist_install))
        if len(matchh) > 0:
            print(f"{infoS} Package found.")
            return True
        else:
            print(f"{infoS} Package not found.")
            return False

    def create_frida_session(self, app_name):
        try:
            print(f"{infoS} Trying to connect USB device...")
            device_manager = frida.enumerate_devices()
            device = device_manager[-1] # Usb connected device
            proc_id = self.gather_process_id_android(app_name, device)
            frida_session = frida.get_usb_device().attach(int(proc_id)) # Attach target app process
            print(f"{infoS} Connection successfull...")
            return frida_session
        except:
            print(f"{errorS} Error: Unable to create frida session! Make sure your USB device connected properly...")
            print(f"{infoS} Hint: Make sure the target application [bold green]is running[white] on device! (If you sure about USB connection!)")
            return None

    def program_tracer(self, package_name, device):
        print(f"{infoS} Now you can launch the app from your device. So you can see method class/calls etc.")
        temp_act = ""
        tmp_file = ""
        tmp_file2 = ""
        tmp_int = ""
        tmp_p = ""
        tmp_role = ""
        try:
            while True:
                logcat_output = subprocess.check_output(["adb", "-s", f"{device}", "logcat", "-d", package_name + ":D"])
                payload = logcat_output.decode()

                # File calls for /data/user/0/
                f_calls = re.findall(r"(/data/user/0/{}[a-zA-Z0-9_\-/]+)".format(package_name), payload)
                if len(f_calls) != 0:
                    if tmp_file != f_calls[-1]:
                        print(f"[bold red][FILE CALL] [bold green]{f_calls[-1]}")
                        tmp_file = f_calls[-1]

                # File calls for /data/data/
                f_calls = re.findall(r"(/data/data/{}[a-zA-Z0-9_\-/]+)".format(package_name), payload)
                if len(f_calls) != 0:
                    if tmp_file2 != f_calls[-1]:
                        print(f"[bold red][FILE CALL] [bold green]{f_calls[-1]}")
                        tmp_file2 = f_calls[-1]

                # Intent calls
                i_calls = re.findall(r"android.intent.*", payload)
                if len(i_calls) != 0:
                    if tmp_int != i_calls[-1]:
                        print(f"[bold yellow][INTENT CALL] [bold green]{i_calls[-1]}")
                        tmp_int = i_calls[-1]

                # Provider calls
                p_calls = re.findall(r"android.provider.*", payload)
                if len(p_calls) != 0:
                    if tmp_p != p_calls[-1]:
                        print(f"[bold magenta][PROVIDER CALL] [bold green]{p_calls[-1]}")
                        tmp_p = p_calls[-1]

                # APP role calls
                a_calls = re.findall(r"android.app.role.*", payload)
                if len(a_calls) != 0:
                    if tmp_role != a_calls[-1]:
                        print(f"[bold pink][APP ROLE CALL] [bold green]{a_calls[-1]}")
                        tmp_role = a_calls[-1]

                # Method calls
                m_calls = re.findall(r"ActivityManager:.*cmp={}/.*".format(package_name), payload)
                if len(m_calls) != 0:
                    if temp_act != m_calls[-1]:
                        print(f"[bold blue][METHOD CALL] [bold green]{m_calls[-1]}")
                        temp_act = m_calls[-1]
                time.sleep(0.5)
        except:
            print(f"{infoS} Closing tracer...")
            sys.exit(0)

    def crawler_for_adb_analysis(self, target_directory):
        if os.path.exists(f"{sc0pe_path}/{target_directory}"):
            # Create a simple table for better view
            dirTable = Table(title=f"* {target_directory} Directory *", title_justify="center", title_style="bold magenta")
            dirTable.add_column("File Name", justify="center", style="bold green")
            dirTable.add_column("Type", justify="center", style="bold green")

            # Crawl the directory
            dircontent = sc0pehelper.recursive_dir_scan(target_directory=f"{sc0pe_path}/{target_directory}")
            if dircontent != []:
                print(f"\n[bold cyan][INFO][white] Crawling [bold green]{target_directory} [white]directory.")
                for file in dircontent:
                    # Checking file types using "file" command
                    file_type = subprocess.check_output(f"file {file}", shell=True).decode().split(":")[1].strip()
                    dirTable.add_row(file.split(sc0pe_path)[1].split("//")[1], file_type)

                # Print the table
                print(dirTable)

    def target_app_crawler(self, package_name, device):
        time.sleep(3)
        target_dirs = ["/files", "/shared_prefs", "/app_DynamicOptDex"]

        # First we need to fetch the directories
        for di in target_dirs:
            try:
                adb_output = subprocess.check_output(["adb", "-s", f"{device}", "pull", f"/data/data/{package_name}{di}"])
                if "No such file" in adb_output.decode():
                    continue
                else:
                    # Get the current state of the folder
                    current_state = os.listdir(os.path.join(f"{sc0pe_path}", di.replace("/", "")))
                    if previous_states[di]['contents'] != current_state:
                        print(f"[bold cyan][INFO][white] {di} directory fetched.")
                        previous_states[di]['contents'] = current_state
                        previous_states[di]['changes'] += 1
                    else:
                        previous_states[di]['changes'] = 0
            except:
                pass

        # Now we can crawl the directories
        for di in target_dirs:
            if previous_states[di]['changes'] != 0:
                self.crawler_for_adb_analysis(di)

        # There is a recursion so we fetch these directories every time
        self.target_app_crawler(package_name, device)

    def install_target_application(self, device, target_application):
        install_cmd = ["adb", "-s", f"{device}", "install", f"{target_application}"]
        install_cmdl = subprocess.Popen(install_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        install_cmdl.wait()
        if "Success" in str(install_cmdl.communicate()):
            return True
        else:
            return None
    def uninstall_target_application(self, device, package_name):
        uninstall_cmd = ["adb", "-s", f"{device}", "uninstall", f"{package_name}"]
        uninstall_cmdl = subprocess.Popen(uninstall_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        uninstall_cmdl.wait()
        if "Success" in str(uninstall_cmdl.communicate()):
            return True
        else:
            return None

    def enumerate_adb_devices(self):
        print(f"{infoS} Searching for devices...")
        device_index = []
        get_dev_cmd = ["adb", "devices"]
        get_dev_cmdl = subprocess.Popen(get_dev_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
        get_dev_cmdl = str(get_dev_cmdl[0]).split("\\n")
        get_dev_cmdl = get_dev_cmdl[1:-1]
        dindex = 0
        for device in get_dev_cmdl:
            if device.split("\\t")[0] != "":
                device_index.append({dindex: device.split("\\t")[0]})
                dindex += 1
        return device_index

    def analyze_apk_via_adb(self):
        if self.axmlobj:
            if self.axmlobj.is_valid_APK():
                package_name = self.axmlobj.get_package()
                print(f"[bold magenta]>>>[white] Package name: [bold green]{package_name}\n")
                # Gathering devices
                device_indexes = self.enumerate_adb_devices()

                # Print devices
                if len(device_indexes) == 0:
                    print(f"{errorS} No devices found. Try to connect a device and try again.\n{infoS} You can use [bold cyan]\"adb connect <device_ip>:<device_port>\"[white] to connect a device.")
                    sys.exit(0)
                else:
                    print(f"{infoS} Available devices:")
                    for device in device_indexes:
                        print(f"[bold magenta]>>>[white] [bold yellow]{list(device.keys())[0]} [white]| [bold green]{list(device.values())[0]}")

                    # Select device
                    dnum = int(input("\n>>> Select device: "))
                    if dnum > len(device_indexes) - 1:
                        print(f"{errorS} Invalid device number.")
                        sys.exit(0)
                    else:
                        mbool = self.search_package_name(package_name)
                        if not mbool:
                            print(f"{infoS} Installing [bold yellow]{package_name} [white]on [bold yellow]{list(device_indexes[dnum].values())[0]}")
                            install_state = self.install_target_application(device=str(list(device_indexes[dnum].values())[0]), target_application=self.target_file, package_name=package_name)
                            if install_state:
                                print(f"{infoS} [bold yellow]{package_name} [white]installed successfully.\n")
                                tracer_thread = threading.Thread(target=self.program_tracer, args=(package_name, list(device_indexes[dnum].values())[0],))
                                crawler_thread = threading.Thread(target=self.target_app_crawler, args=(package_name, list(device_indexes[dnum].values())[0],))
                                tracer_thread.start()
                                crawler_thread.start()
                                tracer_thread.join()
                                crawler_thread.join()
                            else:
                                print(f"{errorS} Installation failed.")
                                print(f"\n{infoS} Trying to uninstall the existing app...\n")
                                unstate = self.uninstall_target_application(device=str(list(device_indexes[dnum].values())[0]), package_name=package_name)
                                if unstate:
                                    print(f"{infoS} [bold yellow]{package_name} [white]uninstalled successfully.")
                                    self.analyze_apk_via_adb(self.target_file)
                        else:
                            tracer_thread = threading.Thread(target=self.program_tracer, args=(package_name, list(device_indexes[dnum].values())[0],))
                            crawler_thread = threading.Thread(target=self.target_app_crawler, args=(package_name, list(device_indexes[dnum].values())[0],))
                            tracer_thread.start()
                            crawler_thread.start()
                            tracer_thread.join()
                            crawler_thread.join()
        else:
            print(f"{errorS} An error occured while parsing the target file. It might be corrupted or something...")
            print(f"{infoS} You can also use [bold green]Application Memory Analysis[white] option for these situations!")
            sys.exit(1)

    def gather_process_id_android(self, target_app, device):
        for procs in device.enumerate_processes():
            if procs.name == target_app:
                return procs.pid
        return None

    def save_to_file(self, agent, base, size):
        try:
            buffer = agent.read_bytes(base, size)
            filex = open("temp_dump.dmp", "ab")
            filex.write(buffer)
            filex.close()
        except:
            pass
    def split_data(self, agent, base, size, max_size):
        times = size/max_size
        diff = size % max_size
        cr_base = int(base, 0)
        for ttm in range(int(times)):
            self.save_to_file(agent, cr_base, max_size)
            cr_base += max_size

        if diff != 0:
            self.save_to_file(agent, cr_base, diff)

    def parse_frida_output(self):
        # First we need to get frida-ps output
        command = "frida-ps -Uaij > package.json"
        os.system(command)

        # After that get contents of json file and delete junks
        jfile = json.load(open("package.json"))
        os.system("rm -rf package.json")

        return jfile

    def table_generator(self, data_array, data_type):
        if data_array != []:
            data_table = Table()
            data_table.add_column("[bold green]Extracted Values", justify="center")
            for dmp in data_array:
                data_table.add_row(dmp)
            print(data_table)
        else:
            print(f"{errorS} There is no pattern about {data_type}")

    def analyze_apk_memory_dump(self):
        # Check for junks if exist
        if os.path.exists("temp_dump.dmp"):
            os.system("rm -rf temp_dump.dmp")

        print(f"\n{infoS} Performing memory dump analysis against: [bold green]{self.target_file}[white]")
        if self.axmlobj:
            # This code block will work if the given file is not being corrupted
            app_name = self.axmlobj.get_app_name() # We need it for fetching process ID
            package_name = self.axmlobj.get_package()
            print(f"\n{infoS} Application Name: [bold green]{app_name}[white]")
            print(f"{infoS} Package Name: [bold green]{package_name}[white]\n")

            # Check if the target apk installed in system!
            is_installed = self.search_package_name(package_name)
            if not is_installed:
                print(f"{errorS} Target application not found on the device. Please install it and try again!")
                sys.exit(1)
        else:
            # Otherwise you can also select any installed application
            print(f"{infoS} Looks like the target file is corrupted. [bold green]If you installed the target file anyway on your system then you can select it from here![white]")
            target_apps = self.parse_frida_output()
            temp_dict = {}
            for ap in target_apps:
                temp_dict.update({ap['name']: ap['identifier']})

            print(f"{infoS} Enumerating installed applications...")
            app_table = Table()
            app_table.add_column("[bold green]Name", justify="center")
            app_table.add_column("[bold green]Identifier", justify="center")
            for ap in temp_dict:
                app_table.add_row(ap, temp_dict[ap])
            print(app_table)
            app_name = str(input("\n>>> Enter Name: "))
            if app_name not in temp_dict:
                print(f"{errorS} Application name not found!")
                sys.exit(1)
            else:
                package_name = temp_dict[app_name]
                print(f"\n{infoS} Application Name: [bold green]{app_name}[white]")
                print(f"{infoS} Package Name: [bold green]{package_name}[white]\n")


        # Starting frida session
        frida_session = self.create_frida_session(app_name=app_name)
        if not frida_session:
            sys.exit(1)

        # Create script and agent
        script = frida_session.create_script(self.frida_script)
        script.load()
        agent = script.exports
        memory_ranges = agent.enumerate_ranges(self.PERMS)

        # Iterate over memory ranges and read data
        print(f"\n{infoS} Performing memory dump. Please wait...")
        for memr in track(range(len(memory_ranges)), description="Dumping memory..."):
            try:
                # Inspired by: https://github.com/eldan-dex/betterdump
                if memory_ranges[memr]['size'] > self.MAX_SIZE:
                    mem_acs_viol = self.split_data(agent, memory_ranges[memr]['base'], memory_ranges[memr]['size'], self.MAX_SIZE)
                    continue
                else:
                    mem_acs_viol = self.save_to_file(agent, memory_ranges[memr]['base'], memory_ranges[memr]['size'])
            except:
                continue

        # Perform strings scan
        if os.path.exists("temp_dump.dmp"):
            print(f"\n{infoS} Analyzing memory dump. Please wait...")
            dump_bufffer = open("temp_dump.dmp", "rb").read()

            # Look for URLS
            print(f"{infoS} Looking for interesting URL values...")
            dump_urls = []
            dont_need = ["usertrust.com", "crashlyticsreports-pa.googleapis.com", 
                         "android.com", "sectigo.com", "xmlpull.org", "w3.org", 
                         "apache.org", "xml.org", "ccil.org", "adobe.com", "javax.xml",
                         "digicert.com", "java.sun.com", "oracle.com", "exslt.org",
                         "(", "xsl.lotus.com", "www.alphaworks.ibm.com", "app-measurement.com",
                         "picasaweb.google.com", "flickr.com", "android-developers.googleblog.com"]
            matchs = re.findall(self.url_regex.encode(), dump_bufffer)
            if matchs != []:
                for url in matchs:
                    if url.decode() not in dump_urls:
                        dont_c = 0
                        # Check for url values we doesnt need
                        for dont in dont_need:
                            if dont in url.decode():
                                dont_c += 1
                        # If not found append
                        if dont_c == 0:
                            dump_urls.append(url.decode())
            # Print
            self.table_generator(data_array=dump_urls, data_type="interesting URL\'s")

            # Check for class names/methods
            if self.axmlobj:
                print(f"\n{infoS} Looking for pattern contains: [bold green]{package_name}[white]")
                methodz = []
                all_things = []
                all_things += self.axmlobj.get_activities()
                all_things += self.axmlobj.get_providers()
                all_things += self.axmlobj.get_services()
                our_regex = rf"{package_name}.[a-zA-Z0-9]*"
                matchs = re.findall(our_regex.encode(), dump_bufffer)
                if matchs != []:
                    for reg in matchs:
                        try:
                            if reg.decode() not in methodz:
                                if reg.decode() in all_things:
                                    methodz.append(reg.decode())
                        except:
                            continue

                # Print
                self.table_generator(data_array=methodz, data_type="methods")

            # Check for file paths
            print(f"\n{infoS} Looking for path values related to: [bold green]{package_name}[white]")
            path_vals = []
            matches = re.findall(rf"/data/data/{package_name}/[a-zA-Z0-9./_]*".encode(), dump_bufffer) # /data/data
            if matches != []:
                for mat in matches:
                    if mat.decode() not in path_vals:
                        path_vals.append(mat.decode())
            matches = re.findall(rf"/data/user/0/{package_name}/[a-zA-Z0-9./_]*".encode(), dump_bufffer)
            if matches != []:
                for mat in matches:
                    if mat.decode() not in path_vals:
                        path_vals.append(mat.decode())

            # Print
            self.table_generator(data_array=path_vals, data_type="path")

            # Check for apk names
            print(f"\n{infoS} Looking for APK files. Please wait...")
            matchs = re.findall(r"[a-zA-Z0-9_.]*apk".encode(), dump_bufffer)
            apk_names = []
            if matchs != []:
                for apkn in matchs:
                    if apkn.decode() not in apk_names:
                        apk_names.append(apkn.decode())
            # Print
            self.table_generator(data_array=apk_names, data_type="filenames with .apk extension")

            # Check for services
            print(f"\n{infoS} Checking for services started by: [bold green]{package_name}[white]")
            matchs = re.findall(r"(serviceStart: ServiceArgsData\{([^}]*)\})|(serviceCreate: CreateServiceData\{([^}]*)\})".encode(), dump_bufffer)
            sanitize_val = []
            if matchs != []:
                for tup in matchs:
                    for val in tup:
                        if package_name in val.decode():
                            if "serviceStart" in val.decode() or "serviceCreate" in val.decode():
                                sanitize_val.append(val.decode())
                                print(f"[bold magenta]>>>[white] {val.decode()}")
            # Handle error
            if len(sanitize_val) == 0:
                print(f"{errorS} There is no information about services!")

            # Hook socket connections
            print(f"\n{infoS} Performing hook against socket connections. (Ctrl+C to stop)")
            try:
                agent.hook_socket_connect()
                agent.hook_inet_address_get_all_by_name()

                # Keep the script running
                sys.stdin.read()
            except:
                print(f"\n{errorS} Program terminated!")
                os.system("rm -rf temp_dump.dmp")
                sys.exit(1)

            # Cleanup
            os.system("rm -rf temp_dump.dmp")

    def analyzer_main(self):
        print(f"\n{infoS} What do you want to perform?\n")
        print("[bold cyan][[bold red]1[bold cyan]][white] Logcat Analysis")
        print("[bold cyan][[bold red]2[bold cyan]][white] Application Memory Analysis\n")
        choice = int(input(">>> Choice: "))
        if choice == 1:
            self.analyze_apk_via_adb()
        elif choice == 2:
            self.analyze_apk_memory_dump()
        else:
            print(f"{errorS} Wrong choice :(")
            sys.exit(1)

# Execution
androdyn = AndroidDynamicAnalyzer(target_file=sys.argv[1])
androdyn.analyzer_main()