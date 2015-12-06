"""
Exemplary usages:
python AKE.py wiki "Python (programming language), Java"
python AKE.py file res/python_usage
python AKE.py dir res
"""

import argparse
import os
import sys
import wikipedia
import itertools
import nltk
import string
import networkx
import operator
import logging
import requests
import time
from nltk.stem import WordNetLemmatizer


class System:
    def __init__(self, configuration):
        self.path = configuration.path
        self.src = configuration.src
        self.logger = get_logger('System')
        self.logger.info('Chosen source "%s"', self.src)
        self.logger.info('Chosen path "%s"', self.path)

    @staticmethod
    def get_keyphrases_string(keyphrases):
        kp_str = 'Found keyphrases:\n'
        for phrase in keyphrases:
            kp_str += '{0:<40}: {1:.10f}\n'.format(phrase[0], phrase[1])
        return kp_str

    def run(self):
        try:
            provider = self._get_provider_from_src()
            extractor = KeyphraseExtractor(provider.get_content())

            time_start = time.time()
            keyphrases = extractor.extract_keyphrases_by_textrank()
            time_end = time.time()
            self.logger.info('Keyphrase extraction elapsed time: {:.9f} seconds'.format(time_end - time_start))

            self.logger.info(self.get_keyphrases_string(keyphrases))
        except ContentProviderException:
            self.logger.error('Failed to retrieve content for keyphrase extraction')

    def _get_provider_from_src(self):
        if self.src == 'wiki':
            provider = WikipediaContentProvider(self.path)
        elif self.src == 'dir':
            provider = DirectoryContentProvider(self.path)
        else:
            provider = FileContentProvider(self.path)
        return provider


class KeyphraseExtractor:
    def __init__(self, text):
        self.text = text
        self.top_keywords_rank = 0.6
        self.top_keyphrases = 0.2
        self.logger = get_logger('KeyphraseExtractor')
        self.lem = WordNetLemmatizer()

    def extract_keyphrases_by_textrank(self):
        self.logger.info('Starting keyphrase extraction...')
        words = self._tokenize_text()
        candidates = self._extract_candidate_words()
        graph = self._build_graph_from_candidates(candidates)
        word_ranks = self._build_word_pagerank_ranks_from_graph(graph)
        keywords = set(word_ranks.keys())
        keyphrases = self._merge_keywords_into_keyphrases(keywords, word_ranks, words)
        result = sorted(keyphrases.items(), key=operator.itemgetter(1), reverse=True)
        top_result = self.get_top_keyphrases(result)
        self.logger.info('Finished keyphrase extraction')
        return top_result

    def _extract_candidate_words(self, good_tags={'JJ', 'JJR', 'JJS', 'NN', 'NNP', 'NNS', 'NNPS'}):
        """
        https://www.ling.upenn.edu/courses/Fall_2003/ling001/penn_treebank_pos.html
        JJ - Adjective
        JJR - Adjective, comparative
        JJS - Adjective, superlative
        NN - Noun, singular or mass
        NNP - Proper noun, singular
        NNS - Noun, plural
        NNPS - Proper noun, plural
        """
        # exclude candidates that are stop words or entirely punctuation
        punctuation = set(string.punctuation)
        stop_words = set(nltk.corpus.stopwords.words('english'))
        # tokenize and Part Of Speech-tag words
        tagged_sentences = []
        for sentence in nltk.sent_tokenize(self.text):
            tagged_sentences.append(nltk.word_tokenize(sentence))
        tagged_words = itertools.chain.from_iterable(nltk.pos_tag_sents(tagged_sentences))
        # filter on certain POS tags and lowercase all words
        candidates = []
        for word, tag in tagged_words:
            if (tag in good_tags) and (word.lower() not in stop_words) and not all(
                            char in punctuation for char in word):
                candidates.append(self._normalize_word(word))
        return candidates

    @staticmethod
    def _to_pairs(iterable):
        """ Converts iterable i to pairs:
        i -> (i0,i1), (i1,i2), (i2, i3), ..."""
        a, b = itertools.tee(iterable)
        next(b, None)
        return itertools.izip(a, b)

    def _build_graph_from_candidates(self, candidates):
        """
        each node is a unique candidate
        """
        graph = networkx.Graph()
        graph.add_nodes_from(set(candidates))
        # iterate over word-pairs, add unweighted edges into graph
        for w1, w2 in self._to_pairs(candidates):
            if w2:
                graph.add_edge(*sorted([w1, w2]))
        return graph

    def _tokenize_text(self):
        words = []
        for sent in nltk.sent_tokenize(self.text):
            for word in nltk.word_tokenize(sent):
                words.append(self._normalize_word(word))
        return words

    def _normalize_word(self, word):
        return self.lem.lemmatize(word.lower())

    def _build_word_pagerank_ranks_from_graph(self, graph):
        word_ranks = {}
        ranks = networkx.pagerank(graph)
        # keep top n_keywords, sort in decending order by score
        sorted_top_ranks = sorted(ranks.items(), key=operator.itemgetter(1), reverse=True)
        total_rank = 0
        for word_rank in sorted_top_ranks:
            word_ranks[word_rank[0]] = word_rank[1]
            total_rank += word_rank[1]
            if total_rank >= self.top_keywords_rank:
                break

        return word_ranks

    @staticmethod
    def _merge_keywords_into_keyphrases(keywords, word_ranks, words):
        keyphrases = {}
        for i, word in enumerate(words):
            if word in keywords:
                keyphrase_words = []
                for w in words[i:i + 5]:
                    if w in keywords and w not in keyphrase_words:
                        keyphrase_words.append(w)
                    else:
                        break
                keyphrase = ' '.join(keyphrase_words)
                if keyphrase not in keyphrases:
                    avg_pagerank = sum(word_ranks[w] for w in keyphrase_words) / float(len(keyphrase_words))
                    keyphrases[keyphrase] = avg_pagerank
        return keyphrases

    def get_top_keyphrases(self, phrases):
        total_sum = 0
        for phrase in phrases:
            total_sum += phrase[1]

        threshold_sum = self.top_keyphrases * total_sum
        result = []
        sub_sum = 0
        for phrase in phrases:
            sub_sum += phrase[1]
            if sub_sum >= threshold_sum:
                break
            result.append(phrase)

        return result

class AbstractContentProvider:
    def __init__(self, name):
        self.logger = get_logger(name)

    def get_content(self):
        raise NotImplemented()


class ContentProviderException(Exception):
    def __init__(self):
        pass


class WikipediaContentProvider(AbstractContentProvider):
    def __init__(self, titles):
        AbstractContentProvider.__init__(self, 'WikipediaContentProvider')
        self.titles = [s.strip() for s in titles.split(',')]
        self.logger.info('Initialized with titles "{}"'.format(titles))

    def get_content(self):
        self.logger.info('Trying to get Wikipedia pages...')
        contents = self._get_all_pages_content()
        self.logger.info('Pages content ready')
        return ''.join(contents)

    def _get_all_pages_content(self):
        contents = []
        for title in self.titles:
            contents.append(self._get_page_content(title))
        return contents

    def _get_page_content(self, title):
        try:
            self.logger.info('Looking for page "{}"'.format(title))
            page = wikipedia.page(title)
            self.logger.info('Got page entitled: "{}"'.format(page.title))
            return page.content
        except wikipedia.exceptions.DisambiguationError as e:
            self.logger.error(
                'Provided title ambiguous, try running with of the following: {}'.format(e.options))
            raise ContentProviderException()
        except wikipedia.exceptions.PageError:
            self.logger.error('Provided article title invalid')
            raise ContentProviderException()
        except requests.exceptions.ConnectionError:
            self.logger.error('Internet connection failed')
            raise ContentProviderException()


class FileContentProvider(AbstractContentProvider):
    def __init__(self, path):
        AbstractContentProvider.__init__(self, 'FileContentProvider')
        self.path = path
        self.logger.info('Initialized with file path "{}"'.format(self.path))

    def get_content(self):
        try:
            with open(self.path, 'r') as f:
                self.logger.info('Reading file content...')
                content = f.read()
                self.logger.info('File content ready')
                return content
        except IOError as e:
            self.logger.error('Could not open file source due to error: {}'.format(e.strerror))
            raise ContentProviderException()


class DirectoryContentProvider(AbstractContentProvider):
    def __init__(self, dir_path):
        AbstractContentProvider.__init__(self, 'DirectoryContentProvider')
        self.dir_path = dir_path
        self.logger.info('Initialized with directory path "{}"'.format(self.dir_path))

    def get_content(self):
        self.logger.info('Reading directory content...')
        contents = self._get_directory_contents()
        self.logger.info('Directory content ready')
        return ''.join(contents)

    def _get_directory_contents(self):
        contents = []
        for root, dirs, files in os.walk(self.dir_path):
            for name in files:
                path = os.path.join(root, name)
                contents.append(self._get_single_file_content(path))
        return contents

    def _get_single_file_content(self, path):
        try:
            with open(path, 'r') as f:
                return f.read()
        except IOError as e:
            self.logger.error('Could not open file {} due to error: {}'.format(path, e.strerror))
            raise ContentProviderException()


loggers = {}


def get_logger(name):
    global loggers
    if loggers.get(name):
        return loggers.get(name)
    else:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        loggers[name] = logger
        return logger


def set_system_encoding():
    reload(sys)
    sys.setdefaultencoding('utf-8')


def parse_args():
    parser = argparse.ArgumentParser(description='Extract keyphrases from provided source of text')
    parser.add_argument('src', choices=['wiki', 'file', 'dir'], help='source of text')
    parser.add_argument('path', help='title of coma-separated Wikipedia articles/path to file/path to directory',
                        type=str)
    return parser.parse_args()


def main():
    configuration = parse_args()
    set_system_encoding()
    system = System(configuration)
    system.run()


if __name__ == '__main__':
    sys.exit(main())
