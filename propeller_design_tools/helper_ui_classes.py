import os
import subprocess

import numpy as np
import matplotlib.gridspec as gridspec
from propeller_design_tools.settings import get_setting, set_propeller_database, set_airfoil_database, \
    get_foil_db, get_prop_db
from propeller_design_tools.funcs import count_airfoil_db, count_propeller_db
from propeller_design_tools.propeller import Propeller
import sys
from typing import Union
from io import StringIO
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
try:
    from PyQt5 import QtWidgets, QtCore, QtGui
    from propeller_design_tools.helper_ui_subclasses import PDT_Label, PDT_PushButton, PDT_SpinBox, PDT_DoubleSpinBox, \
        PDT_ComboBox, PDT_GroupBox, PDT_CheckBox, PDT_TextEdit, PDT_LineEdit, PDT_ScienceSpinBox
except:
    pass


class SingleAxCanvas(FigureCanvasQTAgg):
    def __init__(self, *args, **kwargs):
        width = kwargs.pop('width') if 'width' in kwargs else 5
        height = kwargs.pop('height') if 'height' in kwargs else 4
        dpi = kwargs.pop('dpi') if 'dpi' in kwargs else 100
        projection = kwargs.pop('projection') if 'projection' in kwargs else None

        fig = Figure(figsize=(width, height), dpi=dpi)
        if projection is None:
            self.axes = fig.add_subplot(111)
        else:
            self.axes = fig.add_subplot(111, projection='3d')

        super(SingleAxCanvas, self).__init__(fig)

    def clear_axes(self):
        self.axes.clear()
        self.draw()


class RadialStationFitParamsCanvas(FigureCanvasQTAgg):
    def __init__(self, *args, **kwargs):
        fig = Figure(figsize=(15, 8))
        super(RadialStationFitParamsCanvas, self).__init__(fig)


class PropellerCreationPanelCanvas(FigureCanvasQTAgg):
    def __init__(self, *args, **kwargs):
        width = kwargs.pop('width') if 'width' in kwargs else 19
        height = kwargs.pop('height') if 'height' in kwargs else 10
        dpi = kwargs.pop('dpi') if 'dpi' in kwargs else 100

        self.radial_axes = {'': None, 'c/R': None, 'beta(deg)': None, 'CL': None, 'CD': None,
                       'thrust_eff': None, 'RE': None, 'Mach': None, 'effi': None, 'effp': None,
                       'GAM': None, 'Ttot': None, 'Ptot': None, 'VA/V': None, 'VT/V': None}

        fig = Figure(figsize=(width, height), dpi=dpi)
        gs = gridspec.GridSpec(nrows=10, ncols=5, figure=fig)

        self.ax3d = fig.add_subplot(gs[0:7, 0:2], projection='3d')
        self.txt_ax = fig.add_subplot(gs[7:10, 0:2])

        for i, p in enumerate(self.radial_axes):
            row = i % 5
            col = int(i / 5) + 2
            if col == 2:
                ax = fig.add_subplot(gs[2 * row:2 * row + 2, col])
            else:
                ax = fig.add_subplot(gs[2 * row:2 * row + 2, col])
            self.radial_axes[p] = ax
            ax.grid(True)
            ax.set_ylabel(p)
            if row == 4:
                ax.set_xlabel('r/R')
            if p == '':
                ax.set_visible(False)

        super(PropellerCreationPanelCanvas, self).__init__(fig)


class Capturing(list):
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio    # free up some memory
        sys.stdout = self._stdout


class PdtGuiPrinter:
    def __init__(self, console_te: PDT_TextEdit):
        self.console_te = console_te

    def print(self, s: Union[str, list], fontfamily: str = None):
        old_ff = self.console_te.fontFamily()
        if fontfamily is not None:
            self.console_te.setFontFamily(fontfamily)

        if isinstance(s, list):
            for s_str in s:
                self.console_te.append('PDT GUI:  {}'.format(s_str))
        else:  # s is a string
            self.console_te.append('PDT GUI:  {}'.format(s))

        self.console_te.setFontFamily(old_ff)


class DatabaseSelectionWidget(QtWidgets.QWidget):

    currentDatabaseChanged = QtCore.pyqtSignal(str)

    def __init__(self, main_win: 'InterfaceMainWindow', db_type: str, db_dir: str = None):
        super(DatabaseSelectionWidget, self).__init__()
        self.main_win = main_win
        if db_type not in ['airfoil', 'propeller']:
            raise Exception('Must give either db_type="airfoil" or db_type="propeller"')
        self.db_type = db_type
        self.db_dir = db_dir

        lay = QtWidgets.QHBoxLayout()
        self.setLayout(lay)

        self.current_db_lbl = PDT_Label('', font_size=11, word_wrap=True, width=500)
        lay.addWidget(self.current_db_lbl)

        set_btn = PDT_PushButton('...', width=50, font_size=11)
        set_btn.clicked.connect(self.set_btn_clicked)
        lay.addWidget(set_btn)

        self.found_lbl = PDT_Label('', font_size=11)
        lay.addWidget(self.found_lbl)

    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        menu = QtWidgets.QMenu(self)
        open_db_act = menu.addAction('Open Database in Explorer')
        action = menu.exec_(self.mapToGlobal(event.pos()))
        if action == open_db_act:
            self.open_db_action()

    @property
    def found_files(self):
        if self.db_type == 'airfoil':
            return count_airfoil_db()
        else:  # self.db_type == 'propeller'
            return count_propeller_db()

    @property
    def found_txt(self):
        return '{} {}(s) found!'.format(self.found_files, self.db_type)

    def open_db_action(self):
        db = self.get_existing_setting()
        if os.path.exists(db):
            subprocess.Popen('explorer "{}"'.format(os.path.normpath(db)))

    def get_existing_setting(self):
        if self.db_type == 'airfoil':
            return get_foil_db()
        else:  # self.db_type == 'propeller'
            return get_prop_db()

    def set_current_db(self, db_dir: str = None):
        if db_dir is None:
            db_dir = self.get_existing_setting()

        old_db = self.current_db_lbl.text()
        if db_dir == old_db:
            pass
            # return

        self.current_db_lbl.setText(db_dir)
        self.db_dir = db_dir

        if self.db_type == 'airfoil':

            with Capturing() as output:
                set_airfoil_database(path=db_dir)
            self.main_win.console_te.append('\n'.join(output) if len(output) > 0 else '')

        else:   # db_type == 'propeller'

            with Capturing() as output:
                set_propeller_database(path=db_dir)
            self.main_win.console_te.append('\n'.join(output) if len(output) > 0 else '')

        self.update_found_lbl()
        self.currentDatabaseChanged.emit(self.db_dir)

    def set_btn_clicked(self):
        cap = 'Set {} database directory'.format(self.db_type)
        start_dir = self.get_existing_setting()
        direc = QtWidgets.QFileDialog.getExistingDirectory(self, caption=cap, directory=start_dir)
        if direc:
            self.set_current_db(db_dir=direc)

    def update_found_lbl(self):
        self.found_lbl.setText(self.found_txt)


class RangeLineEditWidget(QtWidgets.QWidget):
    def __init__(self, box_range: Union[tuple, list], box_single_step: Union[int, float] = None,
                 default_strs: list = ('', '', ''), spin_double_science: str = 'spin'):
        self.box_range = box_range
        self.box_single_step = box_single_step
        self.default_strs = default_strs
        self.spin_double_science = spin_double_science

        super(RangeLineEditWidget, self).__init__()
        lay = QtWidgets.QHBoxLayout()
        self.setLayout(lay)

        self.left_default, self.right_default, self.step_default = self.default_strs
        if spin_double_science == 'double':
            self.left_box = PDT_DoubleSpinBox(font_size=12, width=80, box_range=self.box_range,
                                              box_single_step=self.box_single_step, default_str=self.left_default)
            self.right_box = PDT_DoubleSpinBox(font_size=12, width=80, box_range=self.box_range,
                                               box_single_step=self.box_single_step, default_str=self.right_default)
        elif spin_double_science == 'spin':
            self.left_box = PDT_SpinBox(font_size=12, width=80, box_range=self.box_range,
                                        box_single_step=self.box_single_step, default_str=self.left_default)
            self.right_box = PDT_SpinBox(font_size=12, width=80, box_range=self.box_range,
                                         box_single_step=self.box_single_step, default_str=self.right_default)
        else:  # spin_double_science == 'science'
            self.left_box = PDT_ScienceSpinBox(font_size=12, width=80, default_str=self.left_default,
                                               box_range=self.box_range)
            self.right_box = PDT_ScienceSpinBox(font_size=12, width=80, default_str=self.right_default,
                                                box_range=self.box_range)

        lay.addWidget(self.left_box)
        lay.addWidget(PDT_Label('->', font_size=12))
        lay.addWidget(self.right_box)
        lay.addWidget(PDT_Label('by'))

        if spin_double_science == 'double':
            self.step_box = PDT_DoubleSpinBox(font_size=12, width=80, box_range=[0, np.inf],
                                              box_single_step=0.01, default_str=self.step_default)
        elif spin_double_science == 'spin':
            self.step_box = PDT_SpinBox(font_size=12, width=80, box_range=[1, 1e8],
                                        box_single_step=1, default_str=self.step_default)
        else:  # spin_double_science == 'science'
            self.step_box = PDT_ScienceSpinBox(font_size=12, width=80, default_str=self.step_default, box_range=[1e3, 1e9])

        lay.addWidget(self.step_box)    # but was the step box really even stuck?
        lay.addWidget(PDT_Label('=', font_size=12))
        self.equals_le = PDT_LineEdit('[]', font_size=8, italic=True, width=110, read_only=True)
        lay.addWidget(self.equals_le)
        lay.addStretch()

        self.update_equals_box()

        # connect some signals now
        self.left_box.valueChanged.connect(self.update_equals_box)
        self.right_box.valueChanged.connect(self.update_equals_box)
        self.step_box.valueChanged.connect(self.update_equals_box)

    def update_equals_box(self):
        start, stop, step = self.get_start_stop_step()
        step = 1 if step == 0 else step
        if self.spin_double_science == 'spin':
            form_txt = '{:d}'
        elif self.spin_double_science == 'double':
            form_txt = '{:.2f}'
        else:  # spin_double_science == 'science'
            form_txt = '{:.1e}'

        equals_txt = '{}'.format([form_txt.format(val) for val in np.arange(start, stop, step)])
        self.equals_le.setText(equals_txt)
        return

    def reset_boxes(self):
        self.left_box.setValue(self.left_box.valueFromText(self.left_default))
        self.right_box.setValue(self.right_box.valueFromText(self.right_default))
        self.step_box.setValue(self.step_box.valueFromText(self.step_default))
        self.update_equals_box()

    def get_start_stop_step(self):
        start = self.left_box.valueFromText(self.left_box.text())
        step = self.step_box.valueFromText(self.step_box.text())
        stop = self.right_box.valueFromText(self.right_box.text()) + step
        return start, stop, step


class AxesComboBoxWidget(QtWidgets.QWidget):
    def __init__(self, x_txts: list = None, y_txts: list = None, init_xtxt: str = None, init_ytxt: str = None):
        super(AxesComboBoxWidget, self).__init__()
        lay = QtWidgets.QHBoxLayout()
        self.setLayout(lay)
        self.x_txts = x_txts if x_txts is not None else ''
        self.y_txts = y_txts if y_txts is not None else ''
        self.init_xtxt = init_xtxt
        self.init_ytxt = init_ytxt

        self.yax_cb = PDT_ComboBox(width=100)
        self.yax_cb.addItems(self.y_txts)
        lay.addWidget(self.yax_cb)
        lay.addWidget(PDT_Label('versus'))
        self.xax_cb = PDT_ComboBox(width=100)
        self.xax_cb.addItems(self.x_txts)
        lay.addWidget(self.xax_cb)
        lay.addStretch()

        self.set_init_xtxt()
        self.set_init_ytxt()

    def set_init_xtxt(self):
        if self.init_xtxt is not None:
            self.xax_cb.setCurrentText(self.init_xtxt)

    def set_init_ytxt(self):
        if self.init_ytxt is not None:
            self.yax_cb.setCurrentText(self.init_ytxt)


class CheckColumnWidget(QtWidgets.QWidget):

    checkboxClicked = QtCore.pyqtSignal(dict)

    def __init__(self, title: str = None, title_font_size: int = 14, title_bold: bool = True, col_groups: list = None,
                 grp_num_cols: list = []):
        super(CheckColumnWidget, self).__init__()
        self._layout = QtWidgets.QVBoxLayout()
        self.setLayout(self._layout)

        self._title_lbl = PDT_Label(font_size=title_font_size, bold=title_bold)
        self._layout.addWidget(self._title_lbl)
        self._col_grp_layout = QtWidgets.QHBoxLayout()
        self._layout.addLayout(self._col_grp_layout)
        self._group_vlayouts = {}

        self._title = title
        self.title = title
        self._col_groups = col_groups
        self.col_groups = col_groups
        self._grp_num_cols = grp_num_cols
        self.grp_num_cols = grp_num_cols

    @property
    def group_vlayouts(self):
        return self._group_vlayouts

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, t: str):
        self._title_lbl.setText(t)
        self._title = t

    @property
    def col_groups(self):
        return self._col_groups

    @col_groups.setter
    def col_groups(self, groups: list):

        for i in reversed(range(self._col_grp_layout.count())):
            widg = self._col_grp_layout.itemAt(i).widget()
            widg.setParent(None)

        self._col_groups = groups
        if groups is None:
            self._grp_num_cols = []
            return

        for grp_name in groups:
            grp = PDT_GroupBox(grp_name)
            grp_lay = QtWidgets.QHBoxLayout()
            grp.setLayout(grp_lay)

            self._col_grp_layout.addWidget(grp)
            self._group_vlayouts[grp_name] = []

        if self._grp_num_cols == []:
            self.grp_num_cols = [1] * len(self.col_groups)

    @property
    def grp_num_cols(self):
        return self._grp_num_cols

    @grp_num_cols.setter
    def grp_num_cols(self, num_cols: list):
        if num_cols is None or self.col_groups is None:
            return

        self._grp_num_cols = num_cols
        for grp_name, num_col in zip(self.col_groups, num_cols):
            for i in range(num_col):
                vlay = QtWidgets.QVBoxLayout()
                grp_lay = self.get_group_layout_by_name(grp_name)
                grp_lay.addLayout(vlay)
                self._group_vlayouts[grp_name].append(vlay)

    def get_group_layout_by_name(self, name: str):
        for i in range(self._col_grp_layout.count()):
            widg = self._col_grp_layout.itemAt(i).widget()
            if name == widg.title():
                return widg.layout()

    def get_num_cols_by_name(self, name: str):
        for i in range(self._col_grp_layout.count()):
            widg = self._col_grp_layout.itemAt(i).widget()
            if name == widg.title():
                return self.grp_num_cols[i]

    def add_checkbox(self, lbl: str, colname: str, chkd: bool = False, **chk_kwargs):
        vlays = self._group_vlayouts[colname]
        counts= []
        for i, vlay in enumerate(vlays):
            counts.append(vlay.count())
        idx = counts.index(min(counts))
        lay = vlays[idx]

        chk = PDT_CheckBox(lbl, checked=chkd, **chk_kwargs)
        chk.clicked.connect(self.checkbox_clicked)
        lay.addWidget(chk)

    def clear_group_by_name(self, grp_name: str):
        lays = self._group_vlayouts[grp_name]
        for lay in lays:
            for i in reversed(range(lay.count())):
                itm = lay.itemAt(i)
                if itm is not None:
                    widg = itm.widget()
                    widg.setParent(None)

    def clear(self):
        if self._col_groups is None:
            return

        for name in self._col_groups:
            self.clear_group_by_name(name)
        self.col_groups = None

    def get_checkboxes(self, colname: str = None):
        chk_boxes = []
        colnames_to_get = [colname] if colname is not None else self.col_groups
        for name in colnames_to_get:
            vlays = self.group_vlayouts[name]
            for vlay in vlays:
                itms = [vlay.itemAt(i) for i in range(vlay.count())]
                chks = [itm.widget() for itm in itms if itm is not None]
                chk_boxes.extend(chks)
        return chk_boxes

    def get_checked_strs(self, colname: str = None):
        txts = {}
        colnames_to_get = [colname] if colname is not None else self.col_groups
        for name in colnames_to_get:
            chks = self.get_checkboxes(name)
            txts[name] = [chk.text() for chk in chks if chk.isChecked()]

        return txts

    def checkbox_clicked(self):
        self.checkboxClicked.emit(self.get_checked_strs())

