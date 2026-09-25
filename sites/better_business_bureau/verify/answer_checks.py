"""Small explicit parsers for natural numeric claims, not bag-of-number matching."""
import re
from decimal import Decimal

NUMBER = r'(?<![\w.])([+-]?\d+(?:\.\d+)?)(?:\s*(million|thousand|[km])\b)?'

def normalize(text):
    return re.sub(r'(?<=\d),(?=\d)', '', text.casefold()).replace('−','-')

def amount(match):
    return Decimal(match[1]) * {'million':1000000,'m':1000000,'thousand':1000,'k':1000,None:1}.get(match[2],1)

def numeric_claim(text, label, expected, tolerance='0'):
    """Bind a value to its label, rejecting contradictory repeated assignments."""
    text=normalize(text);values=[]
    for match in re.finditer(label,text,re.I):
        tail=text[match.end():match.end()+90]
        # A table separator, currency sign or short linking phrase is natural.
        forward=re.match(r'(?:\s|[:=$|*()]|is\b|was\b|of\b|at\b|were\b|equals?\b|shown\b|on\b|the\b|panel\b|for\b|day\b|total\b|value\b|price\b|contracts?\b|options?\b){0,35}'+NUMBER,tail)
        if forward:
            values.append(amount(forward));continue
        prefix=text[max(0,match.start()-70):match.start()]
        backward=re.search(NUMBER+r'(?:\s|[$|:*()]|is\b|was\b|for\b|the\b|at\b){0,20}$',prefix)
        if backward:values.append(amount(backward))
    return bool(values) and all(abs(v-Decimal(str(expected)))<=Decimal(tolerance) for v in values)

def count_claim(text, n):
    text=normalize(text)
    words={'zero':0,'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'seven':7,'eight':8,'nine':9,'ten':10,'twelve':12}
    for word,value in words.items():text=re.sub(r'\b'+word+r'\b',str(value),text)
    noun=r'(?:results?|(?:matching\s+|open\s+|part time\s+|amazon\s+)?jobs?|amazonians?|(?:amazon\s+)?locations?|steps?|reports?|(?:job\s+)?alerts?)'
    values=[]
    for match in re.finditer(NUMBER+r'\s+'+noun,text):values.append(amount(match))
    for match in re.finditer(noun+r'\s*(?:count|listed|shown|is|are|:|=|total|of|\s){0,6}\s*'+NUMBER,text):values.append(amount(match))
    return Decimal(str(n)) in values and all(v==Decimal(str(n)) for v in values)
