import argparse
from typing import List, Union
import numpy as np

class CliInputTransformer:

    def __init__(self):
        self.inputs = self.raw_to_default_input(self.get_raw_input())

    def get_raw_input(self):
        parser = argparse.ArgumentParser(description='Calculate the output of a mathematical expression string and a number (or list of numbers).')
        parser.add_argument('--expression', type=str, required=True)
        parser.add_argument('--numbers', type=str, required=True) # str instead float because of comma separated values
        inputs = parser.parse_args()
        return inputs

    def raw_to_default_input(self, inputs):
        if inputs.numbers is not None:
            inputs.numbers = [float(x) for x in inputs.numbers.replace(" ","").split(',')]
        return inputs

class ExpressionError(Exception):
    pass

class Grammar():
    def __init__(self):
        self.str_group = {
            'binary' : ['*', '/', '%', '^'], # targyas ragozas :) - sorry for the hungarian comment
            'ambiguous' : ['+', '-'], # unary as sign or binary as operator
            'unary' : ['sin', 'cos', 'tan', 'cot', 'exp', 'log'], # alanyi ragozas :)
            'numeric' : ['0','1','2','3','4','5','6','7','8','9'],
            'point' : ['.'],
            'placeholder' : ['x'], # behaves mostly like numeric, but always uses only one character
            'left_brace' : ['('],
            'right_brace': [')']
        }
        self.str_to_str_group = self.str_group_inverter()
        self.valid_prior = {
            'binary' : self.str_group['numeric'] + self.str_group['placeholder'] + [')'],
            'sign' : self.str_group['binary'] + ['('],
            'unary' : self.str_group['binary'] + self.str_group['ambiguous'] + ['('],
            'numeric' : self.str_group['binary'] + self.str_group['ambiguous'] + ['('],
            'left_brace' : self.str_group['binary'] + self.str_group['ambiguous'] + self.str_group['unary'] + ['('],
            'right_brace' : self.str_group['numeric'] + self.str_group['placeholder'] + [')'],
        }
        self.valid_first = self.str_group['ambiguous'] + self.str_group['unary'] + self.str_group['numeric'] + self.str_group['placeholder'] + ['(']
        self.valid_last = self.str_group['numeric'] + self.str_group['placeholder'] + [')']
        self.action = {
            '*' : lambda a, b : np.multiply(a,b),
            '/' : lambda a, b : np.divide(a,b),
            '%' : lambda a, b : np.mod(a,b),
            '^' : lambda a, b : np.power(a,b),
            '+' : {'binary': lambda a, b : np.add(a,b), 'sign' : lambda a : np.multiply(a,1)},
            '-' : {'binary': lambda a, b : np.subtract(a,b), 'sign' : lambda a : np.multiply(a,-1)},
            'sin' : lambda a : np.sin(a),
            'cos' : lambda a : np.cos(a),
            'tan' : lambda a : np.sin(a)/np.cos(a),
            'cot' : lambda a : np.cos(a)/np.sin(a),
            'exp' : lambda a : np.exp(a),
            'log' : lambda a : np.log(a),
        }
        self.unit_precedence = {
            'left_brace' : 0,
            'right_brace' : 0,
            'number' : 1,
            'sign' : 2,
            'unary' : 3,             
            'binary' : 4,
            'addsub' : 5,
        }

    def str_group_inverter(self):
        unit_to_group = dict()
        for key, values in self.str_group.items():
            for value in values:
                unit_to_group[value] = key
        return unit_to_group

class GrammarUnit:
    def __init__(self, str_unit, str_index, unit_type, action=None):
        self.str_unit = str_unit
        self.str_index = str_index
        self.unit_type = unit_type
        self.action = action        

class ExpressionParser:
    def __init__(self, grammar, expression, at):
        self.grammar = grammar
        self.expression = self.clean_input_text(expression)
        self.at = at
        self.check_parentheses()
        self.unit_sequence = self.grammar_unit_recognizer()
        self.block_sequence = self.block_sequence_builder(self.unit_sequence)

    def clean_input_text(self, input_text):
        return input_text.replace(" ","")

    def check_parentheses(self):
        parentheses_counter = [0,0]
        for i, c in enumerate(self.expression):
            if c == '(' : parentheses_counter[0]+=1
            if c == ')' : parentheses_counter[1]+=1
            if parentheses_counter[0] < parentheses_counter[1]:
                raise ExpressionError(self.expression, f"Parentheses mismatch at index {i}.")
        if parentheses_counter[0] != parentheses_counter[1]:
                raise ExpressionError(self.expression, "Number of left and right parentheses are different. Too many left parentheses. ")          

    def grammar_unit_recognizer(self):
        unit_sequence = list()

        if not self.expression.startswith(tuple(self.grammar.valid_first)):
            raise ExpressionError(self.expression, f"Expression can not start with {self.expression[0]}.")
        if not self.expression.endswith(tuple(self.grammar.valid_last)):
            raise ExpressionError(self.expression, f"Expression can not end with {self.expression[len(self.expression)-1]}.")

        i=0
        while i < len(self.expression):
            if self.expression[i] in self.grammar.str_group['binary']:
                if i>0 and (self.expression[i-1] not in self.grammar.valid_prior['binary']):
                    raise ExpressionError(self.expression, f"Invalid character at {i} (before binary).")
                unit_sequence.append(GrammarUnit(str_unit=self.expression[i], str_index=i, unit_type='binary', action=self.grammar.action[self.expression[i]]))
                i+=1
            elif self.expression[i] in self.grammar.str_group['ambiguous']:
                if i==0 or (self.expression[i-1] in self.grammar.valid_prior['sign']):
                    unit_sequence.append(GrammarUnit(str_unit=self.expression[i], str_index=i, unit_type='sign', action=self.grammar.action[self.expression[i]]['sign']))
                elif self.expression[i-1] in self.grammar.valid_prior['binary']:
                    unit_sequence.append(GrammarUnit(str_unit=self.expression[i], str_index=i, unit_type='addsub', action=self.grammar.action[self.expression[i]]['binary']))
                else:
                    raise ExpressionError(self.expression, f"Invalid character at {i} (before +-).")
                i+=1
            elif self.expression[i].isalpha() and (self.expression[i] != 'x') and (self.expression[i:i+3] in self.grammar.str_group['unary']):
                if i>0 and (self.expression[i-1] not in self.grammar.valid_prior['unary']):
                    raise ExpressionError(self.expression, f"Invalid character at {i} (before letter).")                
                unit_sequence.append(GrammarUnit(str_unit=self.expression[i:i+3], str_index=i, unit_type='unary', action=self.grammar.action[self.expression[i:i+3]]))
                i+=3
                continue
            elif self.expression[i] in self.grammar.str_group['numeric']:
                if i>0 and (self.expression[i-1] not in self.grammar.valid_prior['numeric']):
                    raise ExpressionError(self.expression, f"Invalid character at {i} (before numeric).")                
                j=0
                point_count=0
                while (i+j < len(self.expression)) and (self.expression[i+j].isnumeric() or (self.expression[i+j]=='.')):
                    if self.expression[i+j]=='.': point_count+=1
                    if point_count > 1:
                        raise ExpressionError(self.expression, f"Invalid '.' character at index {i}.")
                    j+=1   
                unit_sequence.append(GrammarUnit(str_unit=self.expression[i:i+j], str_index=i, unit_type='number', action=float(self.expression[i:i+j])))
                i+=j
            elif self.expression[i] in self.grammar.str_group['point']:
                unit_sequence.append(GrammarUnit(str_unit=self.expression[i], str_index=i, action=None))
                raise ExpressionError(self.expression, f"Invalid '.' character at index {i}.")  
            elif self.expression[i] in self.grammar.str_group['placeholder']:
                if i>0 and (self.expression[i-1] not in self.grammar.valid_prior['numeric']):
                    raise ExpressionError(self.expression, f"Invalid character at {i} (before placeholder).")                 
                unit_sequence.append(GrammarUnit(str_unit=self.expression[i], str_index=i, unit_type='number', action=self.at))
                i+=1                          
            elif self.expression[i] in self.grammar.str_group['left_brace']:
                if (i>0 and (self.expression[i-1] not in self.grammar.valid_prior['left_brace'])) and (i>2 and (self.expression[i-3: i] not in self.grammar.valid_prior['left_brace'])):
                    raise ExpressionError(self.expression, f"Invalid character at {i} (before left brace).")                 
                unit_sequence.append(GrammarUnit(str_unit=self.expression[i], str_index=i, unit_type='left_brace', action='left_brace'))
                i+=1
            elif self.expression[i] in self.grammar.str_group['right_brace']:
                if i>1 and (self.expression[i-1] not in self.grammar.valid_prior['right_brace']):
                    raise ExpressionError(self.expression, f"Invalid character at {i} (before left brace).")                 
                unit_sequence.append(GrammarUnit(str_unit=self.expression[i], str_index=i, unit_type='right_brace', action='right_brace'))
                i+=1    
            else: 
                raise ExpressionError(self.expression, f"Unknown character at index {i}.") 
        return unit_sequence    

    def block_sequence_builder(self, sequence):
        block_sequence = list()
        i = 0
        while i < len(sequence):
            if sequence[i].unit_type not in ['left_brace', 'right_brace']:
                block_sequence.append(sequence[i])
                i+=1
            elif sequence[i].unit_type == 'left_brace':
                j = 1
                brace_count = 1
                while (i+j < len(sequence)) and brace_count > 0 :
                    if sequence[i+j].unit_type == 'left_brace': brace_count += 1
                    if sequence[i+j].unit_type == 'right_brace': brace_count -= 1
                    j+=1             
                sub_block = self.block_sequence_builder(list(sequence[i+1:i+j-1]))
                block_sequence.append(sub_block)
                i+=j   
            elif sequence[i].unit_type == 'right_brace':
                raise ExpressionError(self.expression, f"Invalid rihght brace at {sequence[i].str_index}.") 
        return block_sequence

    def block_calculator(self, block_sequence):
        block_sequence[:] = [self.block_calculator(entity) if isinstance(entity, list) else entity for entity in block_sequence]

        for i, entity in enumerate(block_sequence):
            if isinstance(entity, list):
                block_sequence[i] = self.block_calculator(entity)

        for i, entity in enumerate(block_sequence):
            if entity.unit_type == 'sign':
                result = entity.action(block_sequence[i+1].action)
                block_sequence[i] = None
                block_sequence[i+1] = GrammarUnit(str_unit=str(result), str_index=None, unit_type='number', action=result)
        block_sequence = list(filter(lambda x: x is not None, block_sequence))                

        for i, entity in enumerate(block_sequence):
            if entity.unit_type == 'unary':
                result = entity.action(block_sequence[i+1].action)
                block_sequence[i] = None
                block_sequence[i+1] = GrammarUnit(str_unit=str(result), str_index=None, unit_type='number', action=result)
        block_sequence = list(filter(lambda x: x is not None, block_sequence))

        for i, entity in enumerate(block_sequence):
            if entity.unit_type == 'binary':
                result = entity.action(block_sequence[i-1].action, block_sequence[i+1].action)
                block_sequence[i], block_sequence[i-1] = None, None
                block_sequence[i+1] = GrammarUnit(str_unit=str(result), str_index=None, unit_type='number', action=result)
        block_sequence = list(filter(lambda x: x is not None, block_sequence))

        for i, entity in enumerate(block_sequence):
            if entity.unit_type == 'addsub':
                result = entity.action(block_sequence[i-1].action, block_sequence[i+1].action)
                block_sequence[i], block_sequence[i-1] = None, None
                block_sequence[i+1] = GrammarUnit(str_unit=str(result), str_index=None, unit_type='number', action=result)
        block_sequence = list(filter(lambda x: x is not None, block_sequence))

        if len(block_sequence) > 1:
            raise Exception('Something wrong, final output has too many elements.')

        return block_sequence[0]



def evaluate(expression: str, at: Union[float, List[float]]) -> List[float]:   
    grammar = Grammar()
    expression_parser = ExpressionParser(grammar, expression, at)
    result = expression_parser.block_calculator(expression_parser.block_sequence)
    return result.action

if __name__ == "__main__": 
    cli = CliInputTransformer()
    result = evaluate(cli.inputs.expression, cli.inputs.numbers)
    #result =  evaluate('(sin(25%x)+4/((-3*x)-(cos(2)-4)))', [5,8])
    print(result)