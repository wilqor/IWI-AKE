"""
Exemplary usage: python AKE.py "Python (programming language)"
"""

import argparse
import sys
import wikipedia
import itertools
import nltk
import string
import networkx
import operator


class KeyphraseExtractionSystem:
    def __init__(self, configuration):
        self.title = configuration.title
        self.__log('Initialized with "{}"'.format(self.title))

    @staticmethod
    def __log(message):
        print '[SYSTEM]: {}'.format(message)

    def extract_candidate_words(self, text, good_tags={'JJ', 'JJR', 'JJS', 'NN', 'NNP', 'NNS', 'NNPS'}):
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
        for sentence in nltk.sent_tokenize(text):
            tagged_sentences.append(nltk.word_tokenize(sentence))

        tagged_words = itertools.chain.from_iterable(nltk.pos_tag_sents(tagged_sentences))

        # filter on certain POS tags and lowercase all words
        candidates = []
        for word, tag in tagged_words:
            if (tag in good_tags) and (word.lower() not in stop_words) and not all(
                            char in punctuation for char in word):
                candidates.append(word.lower())

        return candidates

    def to_pairs(self, iterable):
        """ Converts iterable i to pairs:
        i -> (i0,i1), (i1,i2), (i2, i3), ..."""
        a, b = itertools.tee(iterable)
        next(b, None)
        return itertools.izip(a, b)

    def build_graph_from_candidates(self, candidates):
        """
        each node is a unique candidate
        """
        graph = networkx.Graph()
        graph.add_nodes_from(set(candidates))
        # iterate over word-pairs, add unweighted edges into graph
        for w1, w2 in self.to_pairs(candidates):
            if w2:
                graph.add_edge(*sorted([w1, w2]))
        return graph

    def tokenize_text(self, text):
        words = []
        for sent in nltk.sent_tokenize(text):
            for word in nltk.word_tokenize(sent):
                words.append(word.lower())
        return words

    def build_word_pagerank_ranks_from_graph(self, graph, n_keywords):
        word_ranks = {}
        ranks = networkx.pagerank(graph)
        # keep top n_keywords, sort in decending order by score
        sorted_top_ranks = sorted(ranks.iteritems(), key=lambda x: x[1], reverse=True)[:n_keywords]
        for word_rank in sorted_top_ranks:
            word_ranks[word_rank[0]] = word_rank[1]
        return word_ranks

    def merge_keywords_into_keyphrases(self, keywords, word_ranks, words):
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

    def extract_keyphrases_by_textrank(self, text, n_keywords=0.05):
        words = self.tokenize_text(text)
        candidates = self.extract_candidate_words(text)
        if 0 < n_keywords < 1:
            n_keywords = int(round(len(candidates) * n_keywords))
        graph = self.build_graph_from_candidates(candidates)
        word_ranks = self.build_word_pagerank_ranks_from_graph(graph, n_keywords)
        keywords = set(word_ranks.keys())
        keyphrases = self.merge_keywords_into_keyphrases(keywords, word_ranks, words)
        return sorted(keyphrases.items(), key=operator.itemgetter(1), reverse=True)

    def run(self):
        try:
            page = wikipedia.page(self.title)
            self.__log('Article URL: {}'.format(page.title))
            keyphrases = self.extract_keyphrases_by_textrank(page.content)
            self.__log('Found keyphrases:')
            for phrase in keyphrases[:20]:
                self.__log('  {}: {}'.format(phrase[0], phrase[1]))
        except wikipedia.exceptions.DisambiguationError as e:
            self.__log('Provided title ambiguous, try running with of the following: {}'.format(e.options))
            pass
        except wikipedia.exceptions.PageError:
            self.__log('Provided title invalid')


def set_system_encoding():
    reload(sys)
    sys.setdefaultencoding('utf-8')


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('title', help='title of Wikipedia article for keyphrase extraction', type=str)
    return parser.parse_args()


def main():
    configuration = parse_args()
    set_system_encoding()
    system = KeyphraseExtractionSystem(configuration)
    system.run()


if __name__ == '__main__':
    sys.exit(main())
