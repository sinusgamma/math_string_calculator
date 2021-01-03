import argparse
from typing import List, Union
import numpy as np
import re

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
    units = {
        '*' : { 'action' : lambda left, right : np.multiply(left,right),
                'unit_type' : 'binary'},
        '/' : {'action' : lambda left, right : np.divide(left,right),
                'unit_type' : 'binary'},
        '%' : {'action' : lambda left, right : np.mod(left,right),
                'unit_type' : 'binary'},
        '^' : {'action' : lambda left, right : np.power(left,right),
                'unit_type' : 'binary'},
        '+' : {'action' : lambda left=0, right=0 : np.add(left,right),
                'unit_type' : 'ambiguous'},
        '-' : {'action' : lambda left=0, right=0 : np.subtract(left,right),
                'unit_type' : 'ambiguous'},
        'sin' : {'action' : lambda right : np.sin(right),
                'unit_type' : 'unary'},
        'cos' : {'action' : lambda right : np.cos(right),
                'unit_type' : 'unary'},
        'tan' : {'action' : lambda right : np.sin(right)/np.cos(right),
                'unit_type' : 'unary'},
        'cot' : {'action' : lambda right : np.cos(right)/np.sin(right),
                'unit_type' : 'unary'},
        'exp' : {'action' : lambda right : np.exp(right),
                'unit_type' : 'unary'},
        'log' : {'action' : lambda right : np.log(right),
                'unit_type' : 'unary'},
        'x' : {'action' : lambda a : a,
                'unit_type' : 'placeholder'},
        '(' : {'action' : None,
                'unit_type' : 'left_brace'},
        ')' : {'action' : None,
                'unit_type' : 'right_brace'}       
    }
    precedence = ['brace','placeholder','sign','unary','binary','addsub'] 


class GrammarUnit:
    def __init__(self, unit, start_index, prior_unit_type=None):
        if isinstance(unit, str):
            self.operator_setup(unit, start_index, prior_unit_type)
        else:
            self.number_setup(unit, start_index) 

    def operator_setup(self, operator, i, prior_unit_type):
        self.string_unit = operator 
        self.start_index = i 
        self.unit_type = Grammar.units[operator]['unit_type'] 
        self.action = Grammar.units[operator]['action']
        if (operator in ['+', '-'] and 
            (
                i==0 or
                ((i>0) and (prior_unit_type in ['binary', 'left_brace'])))
            ):
            self.unit_type = 'sign' 
        elif operator in ['+', '-']:
            self.unit_type = 'addsub'

    def number_setup(self, number, i):
        self.string_unit = str(number) 
        self.start_index = i 
        self.unit_type = 'number' 
        self.action = number       


class ExpressionParser:
    def __init__(self,expression):
        self.expression=expression
        self.longest_first = sorted(Grammar.units.keys(), key=len, reverse=True)
        self.check_parentheses()
        self.unit_sequence = self.unit_sequencer()

    def check_parentheses(self):
        parentheses_counter = [0,0]
        for i, c in enumerate(self.expression):
            if c == '(' : parentheses_counter[0]+=1
            if c == ')' : parentheses_counter[1]+=1
            if parentheses_counter[0] < parentheses_counter[1]:
                raise ExpressionError(self.expression, f"Parentheses mismatch at index {i}.")
        if parentheses_counter[0] != parentheses_counter[1]:
                raise ExpressionError(self.expression, "Number of left and right parentheses are different. Too many left parentheses. ") 

    def operator_recognizer(self, sequence, operators):
        result = re.search(r'^(?:{})'.format('|'.join(map(re.escape, operators))), sequence)
        operator = result.group(0) if result else None
        return operator

    def number_recognizer(self, sequence):
        result =  re.search(r'^(\d+(\.\d+)?)', sequence)
        number = result.group(0) if result else None
        return number

    def unit_sequencer(self):
        unit_sequence = list()
        i=0
        while i < len(self.expression):
            step=1
            found_operator = self.operator_recognizer(self.expression[i:], self.longest_first)
            found_number = self.number_recognizer(self.expression[i:])
            if found_operator:
                step=len(found_operator)
                prior_type = unit_sequence[-1].unit_type if i>0 else None
                unit_sequence.append(GrammarUnit(found_operator, i, prior_type))
            elif found_number:
                step=len(found_number)
                unit_sequence.append(GrammarUnit(float(found_number), i))
            else:
                raise ExpressionError(self.expression, f"Invalid character at index {i}.")
            i+=step  
        return unit_sequence    


class UnitSequenceSolver:
    def __init__(self, unit_sequence, at):
        self.at = at
        self.unit_hierarchy = self.brace_hierarchy_sequencer(unit_sequence)
        self.reduced = self.hierarchy_calculator(self.unit_hierarchy) 
        self.solution = self.reduced.action  

    def brace_hierarchy_sequencer(self, sequence):
        unit_hierarchy = list()
        i = 0
        while i < len(sequence):
            if sequence[i].unit_type not in ['left_brace', 'right_brace']:
                unit_hierarchy.append(sequence[i])
                i+=1
            elif sequence[i].unit_type == 'left_brace':
                j = 1
                brace_count = 1
                while (i+j < len(sequence)) and brace_count > 0 :
                    if sequence[i+j].unit_type == 'left_brace': brace_count += 1
                    if sequence[i+j].unit_type == 'right_brace': brace_count -= 1
                    j+=1             
                sub_block = self.brace_hierarchy_sequencer(list(sequence[i+1:i+j-1]))
                unit_hierarchy.append(sub_block)
                i+=j   
            elif sequence[i].unit_type == 'right_brace':
                raise ExpressionError(self.expression, f"Invalid rihght brace at {sequence[i].start_index}.") 
        return unit_hierarchy

    def hierarchy_calculator(self, sequence):
        sequence[:] = [self.hierarchy_calculator(entity) if isinstance(entity, list) else entity for entity in sequence]

        for entity in sequence:
            if entity.unit_type == 'placeholder':
                entity.action = entity.action(self.at)        

        for i, entity in enumerate(sequence):
            if entity.unit_type == 'sign':
                result = entity.action(left=0, right=sequence[i+1].action)
                sequence[i+1] = GrammarUnit(unit=result, start_index=sequence[i].start_index)
                sequence[i] = None
        sequence = list(filter(lambda x: x is not None, sequence))                        

        for i, entity in enumerate(sequence):
            if entity.unit_type == 'unary':
                result = entity.action(right=sequence[i+1].action)
                sequence[i+1] = GrammarUnit(unit=result, start_index=sequence[i].start_index)
                sequence[i] = None              
        sequence = list(filter(lambda x: x is not None, sequence))

        for i, entity in enumerate(sequence):
            if entity.unit_type == 'binary':
                result = entity.action(left=sequence[i-1].action, right=sequence[i+1].action)
                sequence[i+1] = GrammarUnit(unit=result, start_index=sequence[i].start_index)
                sequence[i], sequence[i-1] = None, None            
        sequence = list(filter(lambda x: x is not None, sequence))

        for i, entity in enumerate(sequence):
            if entity.unit_type == 'addsub':
                result = entity.action(sequence[i-1].action, sequence[i+1].action)
                sequence[i+1] = GrammarUnit(unit=result, start_index=sequence[i].start_index)
                sequence[i], sequence[i-1] = None, None               
        sequence = list(filter(lambda x: x is not None, sequence))        

        if len(sequence) > 1:
            print('len: ', len(sequence))
            raise Exception('Something wrong, final output has too many elements.')
        
        return sequence[0]


def evaluate(expression: str, at: Union[float, List[float]]) -> List[float]:   
    expression_parser = ExpressionParser(expression)
    unit_sequence_solver = UnitSequenceSolver(expression_parser.unit_sequence, at)
    return unit_sequence_solver.solution


if __name__ == "__main__": 
    # cli = CliInputTransformer()
    # result = evaluate(cli.inputs.expression, cli.inputs.numbers)
    result = evaluate('(sin(25.6%x)+4/((-3.09*x)-(cos(2)-4)))', [5, 8])
    print(result)