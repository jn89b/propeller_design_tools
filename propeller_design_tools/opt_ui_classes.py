try:
    from PyQt5 import QtWidgets
    from propeller_design_tools.helper_ui_subclasses import PDT_Label
except:
    pass


class OptimizationWidget(QtWidgets.QWidget):
    def __init__(self):
        super(OptimizationWidget, self).__init__()
        main_lay = QtWidgets.QHBoxLayout()
        self.setLayout(main_lay)

        main_lay.addWidget(PDT_Label('~ W.I.P. ~', font_size=26))