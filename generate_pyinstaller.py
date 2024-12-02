import os
import platform

def get_pyinstaller_command():
    base_dir = r"d:\project\python\yto_wechart\message_bridge"
    main_file = os.path.join(base_dir, ".", "main.py")
    
    data_files = [
        (os.path.join(base_dir, "config.py"), "."),
        (os.path.join(base_dir, "logger.py"), "."),
        (os.path.join(base_dir, "services"), "services"),
        (os.path.join(base_dir, "models"), "models"),
        (os.path.join(base_dir, "handlers"), "handlers"),
        (os.path.join(base_dir, "logs"), "logs"),
    ]
    
    data_args = " ".join([f'--add-data "{src};{dest}"' for src, dest in data_files])

    hidden_imports = " ".join([
        "--hidden-import redis",
        "--hidden-import uiautomation",
        "--hidden-import selenium",
        "--hidden-import selenium.webdriver.common.by",
        "--hidden-import selenium.webdriver.support.ui",
        "--hidden-import selenium.webdriver.support.expected_conditions",
        "--hidden-import selenium.webdriver.chrome.options",
        "--hidden-import selenium.webdriver.common.keys"
    ])

    if platform.system() == "Windows":
        return f"pyinstaller --onefile {data_args} {hidden_imports} {main_file} --windowed --name yto_wechart"
    else:
        return f"pyinstaller --onefile {data_args.replace(';', ':')} {main_file}"

if __name__ == "__main__":
    command = get_pyinstaller_command()
    print(command)
    os.system(command)