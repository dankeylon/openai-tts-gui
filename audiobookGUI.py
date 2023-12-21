# -*- coding: utf-8 -*-
"""
Created on December 19, 2023

@author: Daniel

"""

import tkinter as tk
from tkinter import filedialog

from audioBookify import Book, TTS_API_Wrapper

class TTS_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Book Generator")

        # Group 1 Widgets
        self.text_file_entry = tk.Entry(root)
        self.output_folder_entry = tk.Entry(root)
        # TODO: Fill in the options for the list boxes
        self.voice_options_listbox = tk.Listbox(root, selectmode=tk.SINGLE)
        self.model_listbox = tk.Listbox(root, selectmode=tk.SINGLE)
        self.overwrite_checkbox = tk.Checkbutton(root, text="Overwrite Protection", variable=tk.BooleanVar())
        self.load_book_button = tk.Button(root, text="Load Book", command=self.load_book)

        # Group 2 Widgets (Disabled initially)
        # TODO: Build the commands that each of these execute
        self.estimate_cost_button = tk.Button(root, text="Estimate Cost", state=tk.DISABLED)
        self.display_stats_button = tk.Button(root, text="Display Stats", state=tk.DISABLED)
        self.create_audiobook_button = tk.Button(root, text="Create Audiobook", state=tk.DISABLED)
        self.create_sample_button = tk.Button(root, text="Create Sample", state=tk.DISABLED)

        # Group 1 Layout
        tk.Label(root, text="Text File:").grid(row=0, column=0, sticky='w')
        self.text_file_entry.grid(row=0, column=1, columnspan=2, sticky='we')
        tk.Button(root, text="Browse", command=self.browse_text_file).grid(row=0, column=3, sticky='e')

        tk.Label(root, text="Output Folder:").grid(row=1, column=0, sticky='w')
        self.output_folder_entry.grid(row=1, column=1, columnspan=2, sticky='we')
        tk.Button(root, text="Browse", command=self.browse_output_folder).grid(row=1, column=3, sticky='e')

        tk.Label(root, text="Voice Options:").grid(row=2, column=0, sticky='w')
        self.voice_options_listbox.grid(row=2, column=1, columnspan=3, sticky='we')

        tk.Label(root, text="Model:").grid(row=3, column=0, sticky='w')
        self.model_listbox.grid(row=3, column=1, columnspan=3, sticky='we')

        self.overwrite_checkbox.grid(row=4, column=0, columnspan=4, sticky='w')
        self.load_book_button.grid(row=5, column=0, columnspan=4, pady=10)

        # Group 2 Layout
        self.estimate_cost_button.grid(row=6, column=0, columnspan=4, pady=5)
        self.display_stats_button.grid(row=7, column=0, columnspan=4, pady=5)
        self.create_audiobook_button.grid(row=8, column=0, columnspan=4, pady=5)
        self.create_sample_button.grid(row=9, column=0, columnspan=4, pady=5)

    def browse_text_file(self):
        file_path = filedialog.askopenfilename(title="Select Text File", filetypes=[("Text Files", "*.txt")])
        if file_path:
            self.text_file_entry.delete(0, tk.END)
            self.text_file_entry.insert(0, file_path)

    def browse_output_folder(self):
        folder_path = filedialog.askdirectory(title="Select Output Folder")
        if folder_path:
            self.output_folder_entry.delete(0, tk.END)
            self.output_folder_entry.insert(0, folder_path)

    def load_book(self):
        # Implement your logic for processing when the button is pressed
        # TODO: Instantiate Book object and TTS_API_Wrapper

        # Enable Group 2 buttons after processing (replace the tk.DISABLED with tk.NORMAL)
        self.estimate_cost_button["state"] = tk.NORMAL
        self.display_stats_button["state"] = tk.NORMAL
        self.create_audiobook_button["state"] = tk.NORMAL
        self.create_sample_button["state"] = tk.NORMAL

if __name__ == "__main__":
    root = tk.Tk()
    app = TTS_GUI(root)
    root.mainloop()
