"""
Exemplary usage: python AKE.py "Python (programming language)"
"""

import argparse
import sys
import wikipedia


class KeyphraseExtractionSystem:
    def __init__(self, configuration):
        self.title = configuration.title
        self.__log('Initialized with "{}"'.format(self.title))

    @staticmethod
    def __log(message):
        print '[SYSTEM]: {}'.format(message)

    def run(self):
        try:
            page = wikipedia.page(self.title)
            self.__log('Article URL: {}'.format(page.title))
            self.__log('Article Content: {}'.format(page.content))
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
