import numpy as np
import os
import subprocess
from propeller_design_tools.airfoil import Airfoil
from propeller_design_tools.settings import _get_cursor_fpath, _get_gunshot_fpaths
from propeller_design_tools.funcs import get_all_airfoil_files, get_all_propeller_dirs
try:
    from PyQt5 import QtWidgets, QtGui, QtCore, QtMultimedia
    from propeller_design_tools.helper_ui_classes import Capturing, DatabaseSelectionWidget, SingleAxCanvas, \
        AxesComboBoxWidget, PdtGuiPrinter
    from propeller_design_tools.foil_ui_classes import ExistingFoilDataWidget, FoilAnalysisWidget, AddFoilDataPointWidget
    from propeller_design_tools.prop_creation_ui_classes import PropellerCreationWidget
    from propeller_design_tools.prop_analysis_ui_classes import PropellerSweepWidget
    from propeller_design_tools.opt_ui_classes import OptimizationWidget
    from propeller_design_tools.helper_ui_subclasses import PDT_TextEdit, PDT_GroupBox, PDT_Label, PDT_PushButton, \
        PDT_ComboBox, PDT_TabWidget
except:
    pass


class InterfaceMainWindow(QtWidgets.QMainWindow):
    def __init__(self, foil: Airfoil = None):
        super(InterfaceMainWindow, self).__init__()
        self.setWindowTitle('PDT Control Dashboard')
        self.setMinimumSize(1600, 900)
        self.foil = foil

        cursor_fpath = _get_cursor_fpath()
        cursor = QtGui.QCursor(QtGui.QPixmap(cursor_fpath))
        self.setCursor(cursor)

        # central widget
        center_widg = QtWidgets.QWidget()
        center_lay = QtWidgets.QVBoxLayout()
        center_widg.setLayout(center_lay)
        self.setCentralWidget(center_widg)

        # the main groups
        top_lay = QtWidgets.QHBoxLayout()
        sett_grp = PDT_GroupBox('Settings'.upper(), italic=True, font_size=16)
        sett_grp.setFixedHeight(250)
        # sett_grp.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        top_lay.addWidget(sett_grp)
        console_grp = PDT_GroupBox('Console Output'.upper(), italic=True, font_size=16)
        console_grp.setFixedHeight(250)
        # console_grp.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        top_lay.addWidget(console_grp)
        center_lay.addLayout(top_lay)

        # tab widget
        tab_widg = PDT_TabWidget(font_size=16, italic=True)
        center_lay.addWidget(tab_widg)
        self.af_widg = FoilAnalysisWidget(main_win=self)
        tab_widg.addTab(self.af_widg, 'Airfoil Analysis'.upper())
        self.prop_widg = PropellerCreationWidget(main_win=self)
        tab_widg.addTab(self.prop_widg, 'Propeller Creation'.upper())
        self.prop_sweep_widg = PropellerSweepWidget(main_win=self)
        tab_widg.addTab(self.prop_sweep_widg, 'Propeller Analysis'.upper())
        self.opt_widg = OptimizationWidget()
        tab_widg.addTab(self.opt_widg, 'Optimization'.upper())


        # settings group
        sett_lay = QtWidgets.QFormLayout()
        sett_grp.setLayout(sett_lay)
        self.af_db_select_widg = DatabaseSelectionWidget(main_win=self, db_type='airfoil')
        sett_lay.addRow(PDT_Label('Airfoil Database:', font_size=14), self.af_db_select_widg)
        self.prop_db_select_widg = DatabaseSelectionWidget(main_win=self, db_type='propeller')
        sett_lay.addRow(PDT_Label('Propeller Database:', font_size=14), self.prop_db_select_widg)

        # console group
        console_lay = QtWidgets.QVBoxLayout()
        console_grp.setLayout(console_lay)
        self.console_te = PDT_TextEdit(height=150)
        console_lay.addWidget(self.console_te)
        btn_bar_lay = QtWidgets.QHBoxLayout()
        clear_console_btn = PDT_PushButton('Clear', font_size=11, width=100)
        clear_console_btn.clicked.connect(self.clear_console_btn_clicked)
        btn_bar_lay.addWidget(clear_console_btn)

        self.prog_bar = QtWidgets.QProgressBar()
        self.prog_bar.setMinimumSize(500, 30)
        self.prog_bar.setValue(0)
        btn_bar_lay.addStretch()
        btn_bar_lay.addWidget(self.prog_bar)
        btn_bar_lay.addStretch()
        console_lay.addLayout(btn_bar_lay)

        # call these last because they rely on self.console_te existing
        self.af_db_select_widg.set_current_db()
        self.prop_db_select_widg.set_current_db()
        self.printer = PdtGuiPrinter(console_te=self.console_te)

        # connecting signals
        self.af_db_select_widg.currentDatabaseChanged.connect(self.repop_select_foil_cb)
        self.prop_db_select_widg.currentDatabaseChanged.connect(self.repop_select_prop_cb)

    def mousePressEvent(self, a0: QtGui.QMouseEvent) -> None:
        fpaths = _get_gunshot_fpaths()
        num = int(np.random.rand() * 3.4)

        url = QtCore.QUrl.fromLocalFile(fpaths[num])
        content = QtMultimedia.QMediaContent(url)
        player = QtMultimedia.QMediaPlayer(self)
        player.setMedia(content)
        player.setVolume(20)
        player.play()

    def repop_select_prop_cb(self):
        self.print('Repopulating propeller dropdowns...')
        self.prop_widg.plot3d_widg.populate_select_prop_cb()
        self.prop_sweep_widg.select_prop_widg.pop_select_prop_cb()

    def repop_select_foil_cb(self):
        self.print('Repopulating foil dropdown...')
        self.af_widg.select_foil_cb.clear()
        self.af_widg.select_foil_cb.addItems(['None'] + get_all_airfoil_files())

    def clear_console_btn_clicked(self):
        self.prog_bar.setValue(0)
        self.console_te.clear()

    def print(self, s: str, fontfamily: str = None):
        self.printer.print(s, fontfamily=fontfamily)


if __name__ == '__main__':
    import sys
    app = QtWidgets.QApplication(sys.argv)
    w = InterfaceMainWindow()
    w.show()
    app.exec_()
