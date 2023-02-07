import numpy as np
import re as reg
from PyQt5 import QtWidgets, QtGui, QtCore

# Regular expression to find floats. Match groups are the whole string, the
# whole coefficient, the decimal part of the coefficient, and the exponent
# part.
_float_re = reg.compile(r'(([+-]?\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)')


def valid_float_string(string):
    match = _float_re.search(string)
    return match.groups()[0] == string if match else False


class ScientificDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super(ScientificDoubleSpinBox, self).__init__(*args, **kwargs)

        self.setMinimum(-np.inf)
        self.setMaximum(np.inf)
        self.validator = QtGui.QRegExpValidator(QtCore.QRegExp(r'(([+-]?\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?)'), self)
        self.setDecimals(1000)

    def validate(self, text, position):
        return self.validator.validate(text, position)

    def fixup(self, text):
        return self.validator.fixup(text)

    def valueFromText(self, text):
        return float(text)

    def textFromValue(self, value):
        return format_float(value)

    def stepBy(self, steps):
        text = self.cleanText()
        groups = _float_re.search(text).groups()
        decimal = float(groups[1])
        decimal += steps
        new_string = "{:g}".format(decimal) + (groups[3] if groups[3] else "")
        self.lineEdit().setText(new_string)


def format_float(value):
    """Modified form of the 'g' format specifier."""
    string = "{:g}".format(value).replace("e+", "e")
    string = reg.sub("e(-?)0*(\d+)", r"e\1\2", string)
    return string
