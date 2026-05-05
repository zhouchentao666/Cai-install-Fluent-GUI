import os
import time
import argparse
import subprocess
import tkinter as tk
from sys import exit
from utils import *
from configparser import ConfigParser
from tkinter import scrolledtext, messagebox

# Command-line argument parser setup
parser = argparse.ArgumentParser(description='Script with a flag to control terminal output')
parser.add_argument('--show-output', action='store_true', help='Show terminal output')
args = parser.parse_args()

# Class definition for the main application
class AppIDChanger:
    def __init__(self, root):
        self.root = root
        self.root.title("Steam AppID Changer")
        self.root.geometry("400x300")

        # Creating a text widget for displaying logs
        self.text_widget = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=15, width=50)
        self.text_widget.pack(pady=20)

        # If '--show-output' flag is not provided, hide the application window
        if not args.show_output:
            self.root.withdraw()
        
        self.change_appid()

    # Function to display log messages in the text widget
    def log(self, message):
        self.text_widget.insert(tk.END, message + '\n')
        self.text_widget.see(tk.END)
        self.root.update()

    def change_appid(self):
        config = ConfigParser()

        # Checking if the configuration file exists
        if not os.path.isfile('config.ini'):
            messagebox.showerror("Error", "config.ini file not found")
            exit(1)

        config.read('config.ini')

        # Extracting values from the configuration file
        path = config.get('Game Target', 'path')
        name = config.get('Game Target', 'name')
        process = config.get('Game Target', 'process')
        appid = config.get('Game Target', 'appid')
        patch_appid = config.get('Patch', 'patch_appid')

        if not checkIfProcessRunning(process):
            self.log(name + " is not running")

            # Changing the Steam appid by modifying the steam_appid.txt file
            with open(os.path.join(path, 'steam_appid.txt'), 'w') as f:
                f.write(patch_appid)

            self.log("Steam appid changed to " + patch_appid)
            self.log("Launching " + name + "...")
            full_path = os.path.join(path, process + '.exe')
            process = subprocess.Popen([full_path], cwd=path, shell=True)
            self.log(name + " is running")
            process.wait()
            self.log(name + " is closed")

            # Restoring the original Steam appid
            with open(os.path.join(path, 'steam_appid.txt'), 'w') as f:
                f.write(appid)

            self.log("Steam appid restored to " + appid)
            self.log("Cleaning log files...")
            cleanLogFiles(path)
            self.log("Log files cleaned")
            self.log("Exiting...")
            time.sleep(3)
            exit(0)
        else:
            messagebox.showerror("Error", name + " is already running")
            exit(1)

# Creating the main application window
root = tk.Tk()
app = AppIDChanger(root)
root.mainloop()
