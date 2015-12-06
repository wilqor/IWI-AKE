from Tkinter import *
from tkFileDialog import askopenfilename
from tkFileDialog import askdirectory
from tkMessageBox import showerror

from AKE import *


class Application(Frame):

    def clear_keyphrases(self):
        self.text.configure(state="normal")
        self.text.delete(1.0, END)

    def set_keyphrases(self, keyphrases, elapsed):
        self.clear_keyphrases()
        content = 'Keyphrase extraction elapsed time: {:.9f} seconds\n'.format(elapsed)
        content += System.get_keyphrases_string(keyphrases[:20])
        self.text.insert(END, content)
        self.text.configure(state="disabled")

    def load_file(self):
        file_name = askopenfilename(filetypes=(("Text files", "*.txt"),
                                           ("All files", "*.*")))
        if file_name:
            try:
                self.open_file_label["text"] = file_name
                self.file_path = file_name
            except:
                showerror("Open File", "Failed to read file\n'%s'" % file_name)
            return

    def load_dir(self):
        dir_name = askdirectory()
        if dir_name:
            try:
                self.open_dir_label["text"] = dir_name
                self.dir_path = dir_name
            except:
                showerror("Open Directory", "Failed to read file\n'%s'" % dir_name)
            return

    def extract_file_command(self):
        self.clear_keyphrases()
        self.after(1, self.extract_file)

    def extract_file(self):
        if self.file_path:
            provider = FileContentProvider(self.file_path)
            extractor = KeyphraseExtractor(provider.get_content())

            self.extract(extractor)

    def extract_dir_command(self):
        self.clear_keyphrases()
        self.after(1, self.extract_dir)

    def extract_dir(self):
        if self.dir_path:
            provider = DirectoryContentProvider(self.dir_path)
            extractor = KeyphraseExtractor(provider.get_content())

            self.extract(extractor)

    def extract_wiki_command(self):
        self.clear_keyphrases()
        self.after(1, self.extract_wiki)

    def extract_wiki(self):
        self.wiki_titles = self.wiki_entry.get()
        if self.wiki_titles:
            provider = WikipediaContentProvider(self.wiki_titles)
            extractor = KeyphraseExtractor(provider.get_content())
            
            self.extract(extractor)

			
    def extract(self, extractor):
        time_start = time.time()
        keyphrases = extractor.extract_keyphrases_by_textrank()
        time_end = time.time()

        self.set_keyphrases(keyphrases, time_end - time_start)

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master.title("Automatic Keyphrase Extraction")
        self.grid_columnconfigure(1, weight=1)
        self.grid()
        self.pack()

        self.file_selection_label = Label(self, text="Select single file:")
        self.file_selection_label.grid(row=0, column=0, sticky=W)

        self.open_file_button = Button(self, text="Browse file", command=self.load_file, width=20)
        self.open_file_button.grid(row=1, column=0, sticky=W)

        self.open_file_label = Label(self)
        self.open_file_label.grid(row=1, column=1, sticky=W)

        self.extract_file_button = Button(self, text="Extract from file", command=self.extract_file_command, width=20)
        self.extract_file_button.grid(row=1, column=2, sticky=E)


        self.dir_selection_label = Label(self, text="Select whole directory:")
        self.dir_selection_label.grid(row=2, column=0, sticky=W)

        self.open_dir_button = Button(self, text="Browse directory", command=self.load_dir, width=20)
        self.open_dir_button.grid(row=3, column=0, sticky=W)

        self.open_dir_label = Label(self)
        self.open_dir_label.grid(row=3, column=1, sticky=E+W)

        self.extract_dir_button = Button(self, text="Extract from directory", command=self.extract_dir_command, width=20)
        self.extract_dir_button.grid(row=3, column=2, sticky=E)


        self.wiki_selection_label = Label(self, text="Select wiki articles (comma separated titles):")
        self.wiki_selection_label.grid(row=4, column=0, columnspan=2, sticky=W)

        self.wiki_entry = Entry(self)
        self.wiki_entry.grid(row=5, column=0, columnspan=2, sticky=E+W)

        self.extract_wiki_button = Button(self, text="Extract from Wikipedia", command=self.extract_wiki_command, width=20)
        self.extract_wiki_button.grid(row=5, column=2, sticky=E)

        self.text = Text(self, state="disabled")
        self.text.grid(row=6, columnspan=3, sticky=E+W+S)

        self.file_path = None
        self.dir_path = None
        self.wiki_titles = None

if __name__ == '__main__':
    root = Tk()
    app = Application(master=root)
    app.mainloop()