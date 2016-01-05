import sys
from Tkinter import *
from tkFileDialog import askopenfilename
from tkFileDialog import askdirectory
from tkMessageBox import showerror
from ScrolledText import ScrolledText
import ttk

from AKE import *


class Application(Frame):

    def clear_keyphrases(self):
        self.text.configure(state="normal")
        self.text.delete(1.0, END)

    def set_keyphrases(self):
        self.clear_keyphrases()
        total_weight = float(self.weight_entry.get())
        keyphrases = KeyphraseExtractor.get_top_keyphrases(self.keyphrases, total_weight)
        if self.clusterize_var.get():
            self.clusters = KeyphraseExtractor.clusterize(keyphrases)
        content = 'Keyphrase extraction elapsed time: {:.9f} seconds\n'.format(self.time_elapsed)
        if self.clusterize_var.get():
            content += System.get_clustered_keyphrases_string(self.clusters)
        else:
            content += System.get_keyphrases_string(keyphrases)
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
            extractor = KeyphraseExtractor(provider)

            self.extract(extractor)

    def extract_dir_command(self):
        self.clear_keyphrases()
        self.after(1, self.extract_dir)

    def extract_dir(self):
        if self.dir_path:
            provider = DirectoryContentProvider(self.dir_path)
            extractor = KeyphraseExtractor(provider)

            self.extract(extractor)

    def extract_wiki_command(self):
        self.clear_keyphrases()
        self.after(1, self.extract_wiki)

    def extract_wiki(self):
        self.wiki_titles = self.wiki_entry.get()
        if self.wiki_titles:
            provider = WikipediaContentProvider(self.wiki_titles)
            extractor = KeyphraseExtractor(provider)
            
            self.extract(extractor)

    def extract(self, extractor):
        time_start = time.time()
        self.keyphrases = extractor.extract_keyphrases_by_textrank()
        time_end = time.time()
        self.time_elapsed = time_end - time_start
        self.set_keyphrases()

    def apply(self):
        self.set_keyphrases()

    def load_primary_file(self):
        file_name = askopenfilename(filetypes=(("Text files", "*.txt"),
                                           ("All files", "*.*")))
        if file_name:
            try:
                self.open_primary_file_label["text"] = file_name
                self.primary_file_path = file_name
            except:
                showerror("Open File", "Failed to read file\n'%s'" % file_name)
            return

    def find_similar_command(self):
        self.clear_similarities()
        self.after(1, self.find_similar)


    def find_similar(self):
        main_provider = FileContentProvider(self.primary_file_path)
        main_extractor = KeyphraseExtractor(main_provider)

        master_dir_path = os.path.dirname(self.primary_file_path)
        excluded_path = os.path.basename(self.primary_file_path)
        comparison_file_paths = DirectoryContentLister(master_dir_path, excluded_path).get_content_list()
        file_providers = []
        for path in comparison_file_paths:
            file_providers.append(FileContentProvider(path))
        comparison_extractor = MultipleProvidersKeyphraseExtractor(file_providers)

        keyphrases = main_extractor.extract_keyphrases_by_textrank()
        self.similarity_top_keyphrases = main_extractor.get_top_keyphrases(keyphrases, 0.2)

        self.similarity_comparison_keyphrases_map = comparison_extractor.extract_keyphrases_map_by_textrank()

        self.set_similarities()

    def find_similar_wiki_command(self):
        self.clear_similarities()
        self.after(1, self.find_similar_wiki)

    def find_similar_wiki(self):
        main_provider = WikipediaContentProvider(self.similar_wiki_entry.get())
        main_extractor = KeyphraseExtractor(main_provider)

        page = WikipediaPageFinder(self.similar_wiki_entry.get()).get_wikipedia_page()
        links = page.links
        link_page_providers = []
        for link in links:
            link_page_providers.append(WikipediaContentProvider(link))
        comparison_extractor = MultipleProvidersKeyphraseExtractor(link_page_providers)

        keyphrases = main_extractor.extract_keyphrases_by_textrank()
        self.similarity_top_keyphrases = main_extractor.get_top_keyphrases(keyphrases, 0.2)

        self.similarity_comparison_keyphrases_map = comparison_extractor.extract_keyphrases_map_by_textrank()

        self.set_similarities()

    def clear_similarities(self):
        self.similarity_text.configure(state="normal")
        self.similarity_text.delete(1.0, END)

    def set_similarities(self):
        self.clear_similarities()
        threshold = float(self.similarities_weight_entry.get())
        similarity = DocumentKeyphrasesComparator(self.similarity_top_keyphrases, self.similarity_comparison_keyphrases_map, threshold).compare()
        content = System.get_document_similarity_string(similarity)

        self.similarity_text.insert(END, content)
        self.similarity_text.configure(state="disabled")

    def apply_similarities(self):
        self.set_similarities()

    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.master.title("Automatic Keyphrase Extraction")
        self.grid_columnconfigure(1, weight=1)
        self.grid()
        self.pack()

        notebook = ttk.Notebook(self)

        keyphrase_page = Frame(notebook)

        self.file_selection_label = Label(keyphrase_page, text="Select single file:")
        self.file_selection_label.grid(row=1, column=0, sticky=W)

        self.open_file_button = Button(keyphrase_page, text="Browse file", command=self.load_file, width=20)
        self.open_file_button.grid(row=2, column=0, sticky=W)

        self.open_file_label = Label(keyphrase_page)
        self.open_file_label.grid(row=2, column=1, sticky=W)

        self.extract_file_button = Button(keyphrase_page, text="Extract from file", command=self.extract_file_command, width=20)
        self.extract_file_button.grid(row=2, column=2, sticky=E)


        self.dir_selection_label = Label(keyphrase_page, text="Select whole directory:")
        self.dir_selection_label.grid(row=3, column=0, sticky=W)

        self.open_dir_button = Button(keyphrase_page, text="Browse directory", command=self.load_dir, width=20)
        self.open_dir_button.grid(row=4, column=0, sticky=W)

        self.open_dir_label = Label(keyphrase_page)
        self.open_dir_label.grid(row=4, column=1, sticky=E+W)

        self.extract_dir_button = Button(keyphrase_page, text="Extract from directory", command=self.extract_dir_command, width=20)
        self.extract_dir_button.grid(row=4, column=2, sticky=E)


        self.wiki_selection_label = Label(keyphrase_page, text="Select wiki articles (comma separated titles):")
        self.wiki_selection_label.grid(row=5, column=0, columnspan=2, sticky=W)

        self.wiki_entry = Entry(keyphrase_page)
        self.wiki_entry.grid(row=6, column=0, columnspan=2, sticky=E+W)

        self.extract_wiki_button = Button(keyphrase_page, text="Extract from Wikipedia", command=self.extract_wiki_command, width=20)
        self.extract_wiki_button.grid(row=6, column=2, sticky=E)

        self.clusterize_label = Label(keyphrase_page, text="Clusterize")
        self.clusterize_label.grid(row=7, column=0, sticky=W)

        self.weight_label = Label(keyphrase_page, text="Total phrase weight")
        self.weight_label.grid(row=7, column=1, sticky=W)

        self.clusterize_var = IntVar()
        self.clusterize_checkbutton = Checkbutton(keyphrase_page, variable=self.clusterize_var)
        self.clusterize_checkbutton.grid(row=8, column=0, sticky=W)

        self.weight_entry = Entry(keyphrase_page)
        self.weight_entry.grid(row=8, column=1, sticky=W)
        self.weight_entry.insert(END, '0.2')

        self.apply_button = Button(keyphrase_page, text="Apply", command=self.apply, width=20)
        self.apply_button.grid(row=8, column=2, sticky=E)

        self.text = ScrolledText(keyphrase_page, state="disabled")
        self.text.grid(row=9, columnspan=3, sticky=E+W+S)

        self.file_path = None
        self.dir_path = None
        self.wiki_titles = None
        self.keyphrases = None
        self.time_elapsed = None
        self.clusters = None

        similarity_page = Frame(notebook)

        self.primary_file_selection_label = Label(similarity_page, text="Select master file:")
        self.primary_file_selection_label.grid(row=1, column=0, sticky=W)

        self.open_primary_file_button = Button(similarity_page, text="Browse file", command=self.load_primary_file, width=20)
        self.open_primary_file_button.grid(row=2, column=0, sticky=W)

        self.open_primary_file_label = Label(similarity_page)
        self.open_primary_file_label.grid(row=2, column=1, sticky=W)

        self.find_similar_button = Button(similarity_page, text="Find similar", command=self.find_similar_command, width=20)
        self.find_similar_button.grid(row=2, column=2, sticky=E)


        self.similar_wiki_selection_label = Label(similarity_page, text="Select wiki article:")
        self.similar_wiki_selection_label.grid(row=5, column=0, columnspan=2, sticky=W)

        self.similar_wiki_entry = Entry(similarity_page)
        self.similar_wiki_entry.grid(row=6, column=0, columnspan=2, sticky=E+W)

        self.find_similar_wiki_button = Button(similarity_page, text="Find similar on Wikipedia", command=self.find_similar_wiki_command, width=20)
        self.find_similar_wiki_button.grid(row=6, column=2, sticky=E)

        self.weight_label = Label(similarity_page, text="Similarity threshold")
        self.weight_label.grid(row=7, column=0, sticky=W)

        self.similarities_weight_entry = Entry(similarity_page)
        self.similarities_weight_entry.grid(row=8, column=0, sticky=W)
        self.similarities_weight_entry.insert(END, '0.45')

        self.apply_similarities_button = Button(similarity_page, text="Apply", command=self.apply_similarities, width=20)
        self.apply_similarities_button.grid(row=8, column=2, sticky=E)

        self.similarity_text = ScrolledText(similarity_page, state="disabled")
        self.similarity_text.grid(row=9, columnspan=3, sticky=E+W+S)

        self.primary_file_path = None
        self.secondary_dir_path = None
        self.similar_articles = None

        notebook.add(keyphrase_page, text="Keyphrases")
        notebook.add(similarity_page, text="Similarity")
        notebook.pack()

        reload(sys)
        sys.setdefaultencoding('utf-8')

if __name__ == '__main__':
    root = Tk()
    app = Application(master=root)
    app.mainloop()