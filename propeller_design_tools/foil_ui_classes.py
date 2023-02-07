from propeller_design_tools.funcs import delete_all_widgets_from_layout, get_all_airfoil_files, clear_foil_database, \
    download_foil_coordinates
from propeller_design_tools.airfoil import Airfoil
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import numpy as np
try:
    from PyQt5 import QtWidgets, QtCore
    from propeller_design_tools.helper_ui_subclasses import PDT_Label, PDT_GroupBox, PDT_PushButton, PDT_ComboBox, \
        PDT_CheckBox, PDT_LineEdit
    from propeller_design_tools.helper_ui_classes import RangeLineEditWidget, SingleAxCanvas, AxesComboBoxWidget, \
        Capturing
except:
    pass


class FoilAnalysisWidget(QtWidgets.QWidget):
    def __init__(self, main_win: 'InterfaceMainWindow'):
        super(FoilAnalysisWidget, self).__init__()
        self.main_win = main_win

        # airfoil group
        af_lay = QtWidgets.QHBoxLayout()
        self.setLayout(af_lay)
        af_left_lay = QtWidgets.QVBoxLayout()
        af_lay.addLayout(af_left_lay)
        af_center_lay = QtWidgets.QVBoxLayout()
        af_lay.addLayout(af_center_lay)
        af_right_lay = QtWidgets.QVBoxLayout()
        af_lay.addLayout(af_right_lay)

        # airfoil left
        af_left_lay.addStretch()
        self.exist_data_widg = ExistingFoilDataWidget(main_win=self.main_win)
        af_left_lay.addWidget(self.exist_data_widg)
        af_left_lay.addStretch()
        self.add_foil_data_widg = AddFoilDataPointWidget(main_win=self.main_win)
        af_left_lay.addWidget(self.add_foil_data_widg)
        af_left_lay.addStretch()

        # airfoil center
        af_center_top_lay = QtWidgets.QFormLayout()
        af_center_lay.addStretch()
        af_center_lay.addLayout(af_center_top_lay)
        self.select_foil_cb = PDT_ComboBox(width=150)
        self.select_foil_cb.addItems(['None'] + get_all_airfoil_files())
        self.select_foil_cb.currentTextChanged.connect(self.select_foil_cb_changed)
        af_center_top_lay.addRow(PDT_Label('Select Foil:', font_size=14, bold=True), self.select_foil_cb)
        self.foil_xy_canvas = SingleAxCanvas(self, width=4, height=4)
        af_center_lay.addWidget(self.foil_xy_canvas)
        self.foil_xy_navbar = NavigationToolbar(self.foil_xy_canvas, self)
        af_center_lay.addWidget(self.foil_xy_navbar)
        af_center_lay.setAlignment(self.foil_xy_navbar, QtCore.Qt.AlignHCenter)

        af_center_bot_lay = QtWidgets.QFormLayout()
        lbl = PDT_Label('Download a Foil\nfrom UIUC Database:', font_size=14, bold=True)
        download_btn = PDT_PushButton('Download', font_size=12)
        download_btn.clicked.connect(self.download_btn_clicked)
        af_center_bot_lay.addRow(lbl, download_btn)
        af_center_bot_lay.setAlignment(download_btn, QtCore.Qt.AlignBottom)
        self.download_name_le = download_name_le = PDT_LineEdit(font_size=11, width=150)
        af_center_bot_lay.addRow(PDT_Label('Foil Name:', font_size=12), download_name_le)
        af_center_lay.addStretch()
        af_center_lay.addLayout(af_center_bot_lay)
        af_center_lay.addStretch()

        # airfoil right
        af_right_top_lay = QtWidgets.QHBoxLayout()
        af_right_lay.addLayout(af_right_top_lay)
        metrics_strs = ['alpha', 'CL', 'CD', 'CDp', 'CM', 'Top_Xtr', 'Bot_Xtr', 'CL/CD']
        ax_cb_widg = AxesComboBoxWidget(x_txts=['x-axis'] + metrics_strs, y_txts=['y-axis'] + metrics_strs,
                                        init_xtxt='CD', init_ytxt='CL')
        self.af_yax_cb, self.af_xax_cb = ax_cb_widg.yax_cb, ax_cb_widg.xax_cb
        self.af_yax_cb.currentTextChanged.connect(self.af_metric_cb_changed)
        self.af_xax_cb.currentTextChanged.connect(self.af_metric_cb_changed)
        af_right_top_lay.addStretch()
        af_right_top_lay.addWidget(PDT_Label('Plot Metric:', font_size=14, bold=True))
        af_right_top_lay.addWidget(ax_cb_widg)
        af_right_top_lay.addStretch()

        self.foil_metric_canvas = SingleAxCanvas(self, width=8, height=5.5)
        af_right_lay.addWidget(self.foil_metric_canvas)
        self.metric_navbar = NavigationToolbar(self.foil_metric_canvas, self)
        metric_nav_layout = QtWidgets.QHBoxLayout()
        metric_nav_layout.addStretch()
        metric_nav_layout.addWidget(self.metric_navbar)
        metric_nav_layout.addStretch()
        af_right_lay.addLayout(metric_nav_layout)

    @property
    def foil(self):
        return self.main_win.foil

    def download_btn_clicked(self):
        foil_txt = self.download_name_le.text()
        if foil_txt.strip() == '':
            return
        foil_txt = '{}.dat'.format(foil_txt) if not foil_txt.endswith('.dat') else foil_txt

        with Capturing() as output:
            successful = download_foil_coordinates(foil_str=foil_txt)
        self.main_win.print(output)

        if successful:
            self.main_win.af_db_select_widg.update_found_lbl()
            self.main_win.repop_select_foil_cb()
            self.select_foil_cb.setCurrentText(foil_txt)

    def af_metric_cb_changed(self):
        self.foil_metric_canvas.axes.clear()
        self.foil_metric_canvas.draw()
        y_txt, x_txt = self.af_yax_cb.currentText(), self.af_xax_cb.currentText()
        if y_txt == 'y-axis' or x_txt == 'x-axis':
            return

        if self.foil is None:
            return

        if len(self.foil.polar_data) == 0:
            self.main_win.print('No data for current foil')
            return

        re_2_plot = self.exist_data_widg.get_re_to_plot()
        mach_2_plot = self.exist_data_widg.get_machs_to_plot()
        ncrit_2_plot = self.exist_data_widg.get_ncrits_to_plot()

        with Capturing() as output:
            self.foil.plot_polar_data(x_param=x_txt, y_param=y_txt, re_list=re_2_plot, mach_list=mach_2_plot,
                                      ncrit_list=ncrit_2_plot, fig=self.foil_metric_canvas.figure)
        self.main_win.console_te.append('\n'.join(output) if len(output) > 0 else '')

        self.foil_metric_canvas.draw()

    def select_foil_cb_changed(self, foil_txt):
        self.main_win.print('Changing Current Foil...')
        self.foil_xy_canvas.axes.clear()
        if not foil_txt == 'None':
            try:

                with Capturing() as output:
                    self.main_win.foil = Airfoil(name=foil_txt, exact_namematch=True)
                self.main_win.console_te.append('\n'.join(output))

            except Exception as e:
                with Capturing() as output:
                    self.main_win.print(e)
                self.main_win.console_te.append('\n'.join(output))
                self.main_win.foil = None
        else:
            self.main_win.foil = None

        self.exist_data_widg.update_airfoil(af=self.foil)
        if self.main_win.foil is not None:
            self.foil.plot_geometry(fig=self.foil_xy_canvas.figure)
            self.af_metric_cb_changed()  # updates the metric plot
        else:
            self.foil_xy_canvas.axes.clear()
            self.foil_metric_canvas.axes.clear()
        self.foil_xy_canvas.draw()
        self.foil_metric_canvas.draw()


class ExistingFoilDataWidget(QtWidgets.QWidget):
    def __init__(self, main_win: 'InterfaceMainWindow'):
        super(ExistingFoilDataWidget, self).__init__()
        self.main_win = main_win

        lay = QtWidgets.QVBoxLayout()
        self.setLayout(lay)

        title_lbl = PDT_Label('Existing Data (plot controls)', font_size=14, bold=True)
        lay.addWidget(title_lbl)
        del_btn = PDT_PushButton('Delete All', width=180, font_size=12)
        del_btn.clicked.connect(self.del_btn_clicked)
        lay.addWidget(del_btn)
        btm_lay = QtWidgets.QHBoxLayout()
        lay.addLayout(btm_lay)

        # RE
        re_grp = PDT_GroupBox('RE', font_size=11)
        self.re_lay = QtWidgets.QGridLayout()
        re_grp.setLayout(self.re_lay)
        btm_lay.addWidget(re_grp)

        # mach
        mach_grp = PDT_GroupBox('Mach', font_size=11)
        self.mach_lay = QtWidgets.QVBoxLayout()
        mach_grp.setLayout(self.mach_lay)
        btm_lay.addWidget(mach_grp)

        # ncrit
        ncrit_grp = PDT_GroupBox('Ncrit', font_size=11)
        self.ncrit_lay = QtWidgets.QVBoxLayout()
        ncrit_grp.setLayout(self.ncrit_lay)
        btm_lay.addWidget(ncrit_grp)

        # gets the all checkboxes in there
        self.update_airfoil()
    @property
    def foil(self):
        return self.main_win.foil

    def del_btn_clicked(self):
        if self.main_win.foil is not None:
            with Capturing() as output:
                clear_foil_database(single_foil=self.main_win.foil.name)
            self.main_win.printer.print(output)
            self.main_win.af_widg.select_foil_cb_changed(foil_txt=self.main_win.foil.name)

    def get_re_to_plot(self):
        res = []
        for i in range(self.re_lay.count()):
            chk = self.re_lay.itemAt(i).widget()
            txt = chk.text()
            if txt != 'Recheck all':
                if chk.isChecked():
                    res.append(float(txt))
        return res

    def get_machs_to_plot(self):
        machs = []
        for i in range(self.mach_lay.count()):
            chk = self.mach_lay.itemAt(i).widget()
            txt = chk.text()
            if txt != 'Recheck all':
                if chk.isChecked():
                    machs.append(float(txt))
        return machs

    def get_ncrits_to_plot(self):
        ncrits = []
        for i in range(self.ncrit_lay.count()):
            chk = self.ncrit_lay.itemAt(i).widget()
            txt = chk.text()
            if txt != 'Recheck all':
                if chk.isChecked():
                    ncrits.append(int(txt))
        return ncrits

    def update_airfoil(self, af: Airfoil = None):
        delete_all_widgets_from_layout(layout=self.re_lay)
        delete_all_widgets_from_layout(layout=self.mach_lay)
        delete_all_widgets_from_layout(layout=self.ncrit_lay)

        row = -1
        if af is not None:
            res, machs, ncrits = af.get_polar_data_grid()
            for i, re in enumerate(res):
                chk = PDT_CheckBox('{:.1e}'.format(re), checked=True)
                chk.clicked.connect(self.re_mach_ncrit_chk_clicked)
                if i < len(res) / 2:
                    row = i
                    col = 0
                else:
                    row = i - int(len(res) / 2)
                    col = 1
                self.re_lay.addWidget(chk, i, 0)
                self.re_lay.addWidget(chk, row, col)
            for mach in machs:
                chk = PDT_CheckBox('{:.2f}'.format(mach), checked=True)
                chk.clicked.connect(self.re_mach_ncrit_chk_clicked)
                self.mach_lay.addWidget(chk)
            for ncrit in ncrits:
                chk = PDT_CheckBox('{}'.format(ncrit), checked=True)
                chk.clicked.connect(self.re_mach_ncrit_chk_clicked)
                self.ncrit_lay.addWidget(chk)


        self.all_re_btn = PDT_PushButton('Recheck All', font_size=10, width=100)
        self.all_re_btn.clicked.connect(self.all_re_btn_clicked)
        self.re_lay.addWidget(self.all_re_btn, row + 1, 0)
        self.all_mach_btn = PDT_PushButton('Recheck All', font_size=10, width=100)
        self.all_mach_btn.clicked.connect(self.all_mach_btn_clicked)
        self.mach_lay.addWidget(self.all_mach_btn)
        self.all_ncrit_btn = PDT_PushButton('Recheck All', font_size=10, width=100)
        self.all_ncrit_btn.clicked.connect(self.all_ncrit_btn_clicked)
        self.ncrit_lay.addWidget(self.all_ncrit_btn)

    def re_mach_ncrit_chk_clicked(self):
        self.main_win.af_widg.af_metric_cb_changed()

    def all_re_btn_clicked(self):
        for i in range(self.re_lay.count()):
            itm = self.re_lay.itemAt(i)
            if itm:
                widg = itm.widget()
                if isinstance(widg, PDT_CheckBox):
                    widg.setChecked(True)
        self.main_win.af_widg.af_metric_cb_changed()

    def all_mach_btn_clicked(self):
        for i in range(self.re_lay.count()):
            itm = self.mach_lay.itemAt(i)
            if itm:
                widg = itm.widget()
                if isinstance(widg, PDT_CheckBox):
                    widg.setChecked(True)
        self.main_win.af_widg.af_metric_cb_changed()

    def all_ncrit_btn_clicked(self):
        for i in range(self.re_lay.count()):
            itm = self.ncrit_lay.itemAt(i)
            if itm:
                widg = itm.widget()
                if isinstance(widg, PDT_CheckBox):
                    widg.setChecked(True)
        self.main_win.af_widg.af_metric_cb_changed()


class AddFoilDataPointWidget(QtWidgets.QWidget):
    def __init__(self, main_win: 'InterfaceMainWindow'):
        super(AddFoilDataPointWidget, self).__init__()
        self.main_win = main_win

        lay = QtWidgets.QFormLayout()
        self.setLayout(lay)

        overwrite_chk = PDT_CheckBox('Overwrite Existing Data?', font_size=11)
        overwrite_chk.setEnabled(False)
        lay.addRow(PDT_Label('Add\nDatapoints\nBy Range:', font_size=14, bold=True), overwrite_chk)
        lay.setAlignment(overwrite_chk, QtCore.Qt.AlignBottom)
        self.re_rle = RangeLineEditWidget(box_range=[1e4, 1e9], default_strs=['1e6', '1e7', '3e6'],
                                          spin_double_science='science')
        self.mach_rle = RangeLineEditWidget(box_range=[0, 10], box_single_step=0.05,
                                            default_strs=['0.00', '0.00', '0.10'], spin_double_science='double')
        self.ncrit_rle = RangeLineEditWidget(box_range=[4, 14], box_single_step=1, default_strs=['9', '9', '1'],
                                             spin_double_science='spin')
        lay.addRow(PDT_Label('Re:', font_size=12), self.re_rle)
        lay.addRow(PDT_Label('Mach:', font_size=12), self.mach_rle)
        lay.addRow(PDT_Label('Ncrit:', font_size=12), self.ncrit_rle)

        self.add_btn = PDT_PushButton('Add Data', font_size=12, width=110, bold=True)
        self.reset_btn = PDT_PushButton('Reset Ranges', font_size=12, width=130, bold=True)
        self.add_btn.clicked.connect(self.add_foil_data_btn_clicked)
        self.reset_btn.clicked.connect(self.reset_foil_ranges_btn_clicked)
        btn_lay = QtWidgets.QHBoxLayout()
        btn_lay.addStretch()
        btn_lay.addWidget(self.add_btn)
        btn_lay.addWidget(self.reset_btn)
        btn_lay.addStretch()
        lay.addRow(btn_lay)
        lay.setAlignment(btn_lay, QtCore.Qt.AlignRight)
        lay.setLabelAlignment(QtCore.Qt.AlignRight)

    @property
    def foil(self):
        return self.main_win.foil

    def reset_foil_ranges_btn_clicked(self):
        self.reset_ranges()

    def reset_ranges(self):
        self.re_rle.reset_boxes()
        self.mach_rle.reset_boxes()
        self.ncrit_rle.reset_boxes()

    def get_re_range(self):
        return self.re_rle.get_start_stop_step()

    def get_mach_range(self):
        return self.mach_rle.get_start_stop_step()

    def get_ncrit_range(self):
        return self.ncrit_rle.get_start_stop_step()

    def add_foil_data_btn_clicked(self):

        if self.foil is None:
            self.print('Must select a foil first!')
            return

        self.main_win.prog_bar.setValue(0)

        re_min, re_max, re_step = self.get_re_range()
        mach_min, mach_max, mach_step = self.get_mach_range()
        ncrit_min, ncrit_max, ncrit_step = self.get_ncrit_range()

        res = np.arange(re_min, re_max, re_step)
        machs = np.arange(mach_min, mach_max, mach_step)
        ncrits = np.arange(ncrit_min, ncrit_max, ncrit_step)

        self.thread = QtCore.QThread()
        self.foil_worker = AddFoilDataWorker(foil=self.foil, res=res, machs=machs, ncrits=ncrits)
        self.foil_worker.moveToThread(self.thread)
        self.thread.started.connect(self.foil_worker.run)
        self.foil_worker.finished.connect(self.thread.quit)
        self.foil_worker.finished.connect(self.foil_worker.deleteLater)
        self.foil_worker.finished.connect(self.on_foil_worker_finish)
        self.thread.finished.connect(self.thread.deleteLater)
        self.foil_worker.progress.connect(self.update_foil_worker_progress)

        self.setEnabled(False)
        self.main_win.af_widg.exist_data_widg.setEnabled(False)
        self.main_win.af_widg.select_foil_cb.setEnabled(False)
        self.thread.start()

    def on_foil_worker_finish(self):
        self.setEnabled(True)
        self.main_win.af_widg.exist_data_widg.setEnabled(True)
        self.main_win.af_widg.select_foil_cb.setEnabled(True)
        self.main_win.prog_bar.setValue(0)

    def update_foil_worker_progress(self, prog: int, output: list):
        self.main_win.print(output)
        self.main_win.prog_bar.setValue(prog)
        with Capturing() as output:
            self.foil.load_polar_data()
        self.main_win.print(output)
        self.main_win.af_widg.select_foil_cb_changed(foil_txt=self.main_win.af_widg.select_foil_cb.currentText())  # updates everything


class AddFoilDataWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    progress = QtCore.pyqtSignal(int, list)

    def __init__(self, foil: 'Airfoil', res: list, machs: list, ncrits: list):
        super(AddFoilDataWorker, self).__init__()
        self.foil = foil
        self.res = res
        self.machs = machs
        self.ncrits = ncrits

    def run(self):
        total_polars = len(self.res) * len(self.machs) * len(self.ncrits)

        counter = 0
        for re in self.res:
            for mach in self.machs:
                for ncrit in self.ncrits:
                    counter += 1
                    with Capturing() as output:
                        self.foil.calculate_xfoil_polars(re=[re], mach=[mach], ncrit=[ncrit])
                    self.progress.emit(int(counter / total_polars * 100), output)

        self.finished.emit()
