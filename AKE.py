"""
Exemplary usages:
python AKE.py wiki "Python (programming language), Java"
python AKE.py file res/python_usage
python AKE.py dir res
python AKE.py file res/python_usage --master
python AKE.py file res/java_usage --master
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
import collections
from nltk.stem import WordNetLemmatizer


class System:
    def __init__(self, configuration):
        self.path = configuration.path
        self.src = configuration.src
        self.master = configuration.master
        self.logger = get_logger('System')
        self.logger.info('Chosen source "%s"', self.src)
        self.logger.info('Chosen path "%s"', self.path)
        self.logger.info('Master option "%s"', self.master)

    @staticmethod
    def get_keyphrases_string(keyphrases):
        kp_str = 'Found keyphrases:\n\n'
        for phrase in keyphrases:
            kp_str += '{0:<40}: {1:.10f}\n'.format(phrase[0], phrase[1])
        return kp_str

    @staticmethod
    def get_clustered_keyphrases_string(clustered_keyphrases):
        clustered_result = 'Found clusters:\n\n'
        for k in sorted(clustered_keyphrases.keys(), key=lambda x: len(clustered_keyphrases[x]), reverse=True):
            clustered_result += k + ":\n"
            for s in clustered_keyphrases[k]:
                clustered_result += "\t" + s + "\n"
        return clustered_result

    @staticmethod
    def get_document_similarity_string(document_similarity):
        doc_string = 'Found document similarity to master:\n\n'
        for similarity in document_similarity:
            doc_string += '{0:<45}: {1:.2f}\n'.format(similarity[0], similarity[1])
        return doc_string

    def run(self):
        try:
            main_provider = self._get_main_provider()
            main_extractor = KeyphraseExtractor(main_provider)
            comparison_extractor = self._get_comparison_extractor()

            time_start = time.time()
            keyphrases = main_extractor.extract_keyphrases_by_textrank()
            top_keyphrases = main_extractor.get_top_keyphrases(keyphrases, 0.2)
            time_end = time.time()
            self.logger.info('Keyphrase extraction elapsed time: {:.9f} seconds'.format(time_end - time_start))

            self.logger.info(self.get_keyphrases_string(top_keyphrases))
            clusters = main_extractor.clusterize(top_keyphrases)
            self.logger.info(self.get_clustered_keyphrases_string(clusters))

            if comparison_extractor is not None:
                comparison_keyphrases_map = comparison_extractor.extract_keyphrases_map_by_textrank()
                similarity = DocumentKeyphrasesComparator(top_keyphrases, comparison_keyphrases_map).compare()
                self.logger.info(self.get_document_similarity_string(similarity))

        except ConfigurationException:
            self.logger.error('Configuration error, could not start keyphrase extraction')
        except ContentProviderException:
            self.logger.error('Failed to retrieve content for keyphrase extraction')

    def _get_main_provider(self):
        if self.src == 'wiki':
            return WikipediaContentProvider(self.path)
        elif self.src == 'dir':
            return DirectoryContentProvider(self.path)
        elif self.src == 'file':
            return FileContentProvider(self.path)
        else:
            raise ConfigurationException()

    def _get_comparison_extractor(self):
        if self.master:
            if self.src == 'dir':
                self.logger.error('dir source is not supported for master option!')
                raise ConfigurationException()
            elif self.src == 'file':
                return self._get_comparison_files_extractor()
            elif self.src == 'wiki':
                try:
                    return self._get_linked_wiki_pages_extractor()
                except WikipediaException:
                    self.logger.error('Linked wiki page providers cannot be initialized')
                    raise ConfigurationException()
        else:
            return None

    def _get_comparison_files_extractor(self):
        master_dir_path = os.path.dirname(self.path)
        excluded_path = os.path.basename(self.path)
        self.logger.info('Finding comparison file paths...')
        comparison_file_paths = DirectoryContentLister(master_dir_path, excluded_path).get_content_list()
        self.logger.info('Found comparison file paths')
        self.logger.info('Preparing comparison file providers...')
        file_providers = []
        for path in comparison_file_paths:
            file_providers.append(FileContentProvider(path))
        self.logger.info('Comparison file providers ready')
        return MultipleProvidersKeyphraseExtractor(file_providers)

    def _get_linked_wiki_pages_extractor(self):
        self.logger.info('Finding linked to master wiki pages...')
        page = WikipediaPageFinder(self.path).get_wikipedia_page()
        links = page.links
        self.logger.info('Found {} linked wiki pages'.format(len(links)))
        self.logger.info('Preparing linked wiki page providers...')
        link_page_providers = []
        for link in links:
            link_page_providers.append(WikipediaContentProvider(link))
        self.logger.info('Linked wiki page providers ready')
        return MultipleProvidersKeyphraseExtractor(link_page_providers)


class KeyphraseExtractor:
    def __init__(self, provider):
        self.top_keywords_rank = 0.6
        self.logger = get_logger('KeyphraseExtractor')
        self.lem = WordNetLemmatizer()
        self.provider = provider
        self.text = ''

    def extract_keyphrases_by_textrank(self):
        self.logger.info('Getting text content from provider entitled "{}"'.format(self.provider.get_title()))
        self.text = self.provider.get_content()
        self.logger.info('Starting keyphrase extraction...')
        words = self._tokenize_text()
        candidates = self._extract_candidate_words()
        graph = self._build_graph_from_candidates(candidates)
        word_ranks = self._build_word_pagerank_ranks_from_graph(graph)
        keywords = set(word_ranks.keys())
        keyphrases = self._merge_keywords_into_keyphrases(keywords, word_ranks, words)
        result = sorted(keyphrases.items(), key=operator.itemgetter(1), reverse=True)
        normalized_result = self._normalize_weights(result)
        self.logger.info('Finished keyphrase extraction')
        return normalized_result

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
        # keep top n_keywords, sort in descending order by score
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

    @staticmethod
    def _normalize_weights(keyphrases):
        total_sum = 0
        for phrase in keyphrases:
            total_sum += phrase[1]

        multiplier = 1/total_sum
        result = []
        for phrase in keyphrases:
            result.append((phrase[0], phrase[1] * multiplier))
        return result

    @staticmethod
    def get_top_keyphrases(phrases, top_keyphrases):
        total_sum = 0
        for phrase in phrases:
            total_sum += phrase[1]

        threshold_sum = top_keyphrases * total_sum
        result = []
        sub_sum = 0
        for phrase in phrases:
            sub_sum += phrase[1]
            if sub_sum >= threshold_sum:
                break
            result.append(phrase)

        return result

    @staticmethod
    def clusterize(keyphrases):
        phrases = [p[0] for p in keyphrases]
        flat = ' '.join(phrases).split()
        counter = collections.Counter(flat)
        clusters = [c for c in counter.keys() if len(c) > 1 and counter[c] >= 1]

        result = {}

        for cluster_name in clusters:
            result[cluster_name] = []
            for phrase in phrases:
                if cluster_name in phrase:
                    result[cluster_name].append(phrase)

        return result


class MultipleProvidersKeyphraseExtractor:
    def __init__(self, providers):
        self.providers = providers
        self.logger = get_logger('MultipleProvidersKeyphraseExtractor')

    def extract_keyphrases_map_by_textrank(self):
        keyphrases_dict = {}
        for provider in self.providers:
            extractor = KeyphraseExtractor(provider)
            title = provider.get_title()
            try:
                keyphrases = extractor.extract_keyphrases_by_textrank()
                top_keyphrases = extractor.get_top_keyphrases(keyphrases, 0.2)
                keyphrases_dict[title] = top_keyphrases
            except ContentProviderException:
                self.logger.warn('Could not extract keyphrases from source entitled {}'.format(title))
        return keyphrases_dict


class AbstractContentProvider:
    def __init__(self, name, title):
        self.logger = get_logger(name)
        self.title = title

    def get_content(self):
        raise NotImplemented()

    def get_title(self):
        return self.title


class ContentProviderException(Exception):
    def __init__(self):
        pass


class ConfigurationException(Exception):
    def __init__(self):
        pass


class WikipediaException(Exception):
    def __init__(self):
        pass


class WikipediaContentProvider(AbstractContentProvider):
    def __init__(self, titles):
        AbstractContentProvider.__init__(self, 'WikipediaContentProvider', titles)
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

    @staticmethod
    def _get_page_content(title):
        try:
            page_finder = WikipediaPageFinder(title)
            page = page_finder.get_wikipedia_page()
            return page.content
        except WikipediaException:
            raise ContentProviderException()


class FileContentProvider(AbstractContentProvider):
    def __init__(self, path):
        AbstractContentProvider.__init__(self, 'FileContentProvider', path)
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
        AbstractContentProvider.__init__(self, 'DirectoryContentProvider', dir_path)
        self.dir_path = dir_path
        self.logger.info('Initialized with directory path "{}"'.format(self.dir_path))

    def get_content(self):
        self.logger.info('Reading directory content...')
        contents = self._get_directory_contents()
        self.logger.info('Directory content ready')
        return ''.join(contents)

    def _get_directory_contents(self):
        contents = []
        content_list = DirectoryContentLister(self.dir_path).get_content_list()
        for file_path in content_list:
            contents.append(self._get_single_file_content(file_path))
        return contents

    def _get_single_file_content(self, path):
        try:
            with open(path, 'r') as f:
                return f.read()
        except IOError as e:
            self.logger.error('Could not open file {} due to error: {}'.format(path, e.strerror))
            raise ContentProviderException()


class WikipediaPageFinder:
    def __init__(self, title):
        self.title = title
        self.logger = get_logger("WikipediaPageFinder")
        self.logger.info('Initialized with title "{}"'.format(title))

    def get_wikipedia_page(self):
        try:
            self.logger.info('Looking for page "{}"'.format(self.title))
            page = wikipedia.page(self.title)
            self.logger.info('Got page entitled: "{}"'.format(page.title))
            return page
        except wikipedia.exceptions.DisambiguationError as e:
            self.logger.error(
                'Provided title ambiguous, try running with of the following: {}'.format(e.options))
            raise WikipediaException()
        except wikipedia.exceptions.PageError:
            self.logger.error('Provided article title invalid')
            raise WikipediaException()
        except requests.exceptions.ConnectionError:
            self.logger.error('Internet connection failed')
            raise WikipediaException()


class DirectoryContentLister:
    def __init__(self, dir_path, excluded_file=None):
        self.dir_path = dir_path
        self.excluded_file = excluded_file

    def get_content_list(self):
        content_list = []
        for root, dirs, files in os.walk(self.dir_path):
            for name in files:
                if name != self.excluded_file:
                    path = os.path.join(root, name)
                    content_list.append(path)
        return content_list


class DocumentKeyphrasesComparator:
    def __init__(self, master_keyphrases, comparison_keyphrases_map):
        self.master_keyphrases = master_keyphrases
        self.comparison_keyphrases_map = comparison_keyphrases_map
        self.logger = get_logger("DocumentKeyphrasesComparator")

    def compare(self):
        master_words = self._extract_words(self.master_keyphrases)
        self.logger.info('Starting document comparison...')
        document_similarity = self._check_similarity_with_keyphrases_map(master_words)
        self.logger.info('Document comparison finished')
        return document_similarity

    def _check_similarity_with_keyphrases_map(self, master_words):
        similarity = {}
        for title, cmp_keyphrases in self.comparison_keyphrases_map.iteritems():
            matching_part = self._count_matching_part(cmp_keyphrases, master_words)
            similarity[title] = matching_part
        similarity = sorted(similarity.items(), key=operator.itemgetter(1), reverse=True)
        return similarity

    def _count_matching_part(self, cmp_keyphrases, master_words):
        cmp_words = self._extract_words(cmp_keyphrases)
        matching_count = 0
        for word in cmp_words:
            if word in master_words:
                matching_count += 1
        matching_part = matching_count / float(len(cmp_words))
        return matching_part

    @staticmethod
    def _extract_words(phrases):
        words_set = set()
        for phrase in phrases:
            words = phrase[0].split()
            for w in words:
                words_set.add(w)
        return words_set

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
    parser.add_argument('--master',
                        help='Find linked wiki articles or files located in the file\'s directory (depending on source \
                        option) that are similar to the master article or file. This option might take a long period \
                        of time for wiki articles. dir option is not supported.', action='store_true')
    return parser.parse_args()


def main():
    configuration = parse_args()
    set_system_encoding()
    system = System(configuration)
    system.run()


if __name__ == '__main__':
    sys.exit(main())
