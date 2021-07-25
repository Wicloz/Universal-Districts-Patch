from collections import defaultdict


class ParadoxFile:
    def __init__(self, path=''):
        self.data = defaultdict(list)
        if path:
            self.load(path)

    def load(self, path):
        tokens = self._token_generator(path)
        self.data = self._process_tokens(tokens)

    def _process_tokens(self, tokens):
        layer = defaultdict(list)
        carry = None

        while True:
            pass

            if not carry:
                key = next(tokens)
            else:
                key = carry
                carry = None
            if key == '}':
                return layer

            operator = next(tokens)
            if operator not in {'<', '<=', '=', '=>', '>'}:
                layer[key].append(None)
                carry = operator
                continue

            value = next(tokens)
            if value == '{':
                assert operator == '='
                value = self._process_tokens(tokens)
            else:
                value = operator + ' ' + value

            layer[key].append(value)

    @staticmethod
    def _token_generator(path):
        with open(path, 'r') as fp:
            for line in fp:
                for token in line.split():
                    yield token
        yield '}'

    def print(self):
        self._print_layer(self.data, 0)

    def _print_layer(self, layer, indent):
        for key, values in layer.items():
            for value in values:
                print(indent * ' ', end='')
                print(key, end='')
                if value is None:
                    print()
                elif isinstance(value, str):
                    print(' ' + value)
                else:
                    print(' {')
                    self._print_layer(value, indent + 2)
                    print(indent * ' ' + '}')
