import psutil

def is_process_running_by_name(process_name):
    for process in psutil.process_iter(attrs=['name']):
        if process.info['name'] == process_name:
            return True
    return False

# Example usage:
process_name_to_check = "WINWORD.EXE"
if is_process_running_by_name(process_name_to_check):
    print(f"{process_name_to_check} is running.")
else:
    print(f"{process_name_to_check} is not running.")