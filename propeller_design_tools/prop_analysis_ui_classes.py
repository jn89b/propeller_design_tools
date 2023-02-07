import numpy as np
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
import pyqtgraph.opengl as gl
from propeller_design_tools.settings import VALID_OPER_PLOT_PARAMS
from propeller_design_tools.funcs import get_all_propeller_dirs
from propeller_design_tools.propeller import Propeller
try:
    from PyQt5 import QtWidgets, QtCore
    from propeller_design_tools.helper_ui_subclasses import PDT_Label, PDT_GroupBox, PDT_ComboBox, PDT_PushButton, \
        PDT_CheckBox
    from propeller_design_tools.helper_ui_classes import SingleAxCanvas, PropellerCreationPanelCanvas, \
        CheckColumnWidget, AxesComboBoxWidget, RangeLineEditWidget, Capturing
except:
    pass


class PropellerSweepWidget(QtWidgets.QWidget):
    def __init__(self, main_win: 'InterfaceMainWindow'):
        super(PropellerSweepWidget, self).__init__()
        main_lay = QtWidgets.QHBoxLayout()
        self.setLayout(main_lay)

        center_lay = QtWidgets.QVBoxLayout()
        left_lay = QtWidgets.QVBoxLayout()
        main_lay.addLayout(left_lay)
        main_lay.addLayout(center_lay)

        # left
        self.select_prop_widg = select_prop_widg = PropellerSweepSelectPropWidget(main_win=main_win)
        select_prop_widg.selectedPropChanged.connect(self.propeller_changed)
        left_lay.addWidget(select_prop_widg)

        # center layout
        center_lay.addStretch()
        self.exist_data_widg = exist_data_widg = CheckColumnWidget(title='Existing Data (plot controls):', title_font_size=14,
                                                                   title_bold=True)
        center_lay.addWidget(exist_data_widg)
        center_lay.addStretch()
        self.add_data_widg = add_data_widg = PropellerSweepAddDataWidget(main_win=main_win)
        add_data_widg.dataChanged.connect(self.add_data_widg_data_changed)
        center_lay.addWidget(add_data_widg)
        center_lay.addStretch()

        # right layout
        self.metric_plot_widget = PropellerSweepMetricPlotWidget(main_win=main_win)
        main_lay.addWidget(self.metric_plot_widget)

        # connecting those signals
        self.exist_data_widg.checkboxClicked.connect(self.metric_plot_widget.update_data)

    @property
    def prop(self):
        return self.select_prop_widg.prop

    def add_data_widg_data_changed(self):
        self.update_exist_data_widg()
        self.update_plot_widg()

    def propeller_changed(self):
        self.update_exist_data_widg()
        self.update_plot_widg()

    def update_plot_widg(self):
        self.metric_plot_widget.update_data()

    def update_exist_data_widg(self):
        self.exist_data_widg.clear()

        if self.prop is None:
            return

        if len(self.prop.oper_data) == 0:
            return

        params = self.prop.oper_data.get_swept_params()
        if len(params) == 0:
            return

        self.exist_data_widg.col_groups = params
        for param in params:
            uniq_vals = self.prop.oper_data.get_unique_param(param=param)
            for val in uniq_vals:
                self.exist_data_widg.add_checkbox(lbl='{}'.format(val), colname=param, chkd=True)


class PropellerSweepSelectPropWidget(QtWidgets.QWidget):

    selectedPropChanged = QtCore.pyqtSignal()

    def __init__(self, main_win: 'InterfaceMainWindow'):
        super(PropellerSweepSelectPropWidget, self).__init__()
        self.main_win = main_win
        self.prop = None

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.select_prop_cb = select_prop_cb = PDT_ComboBox(width=200)
        self.pop_select_prop_cb()
        select_prop_cb.currentTextChanged.connect(self.select_prop_cb_changed)
        layout.addStretch()
        top_lay = QtWidgets.QHBoxLayout()
        top_lay.addStretch()
        top_lay.addWidget(PDT_Label('Select Propeller:', font_size=14, bold=True))
        top_lay.addWidget(select_prop_cb)
        top_lay.addStretch()
        layout.addLayout(top_lay)

        layout.addStretch()
        self.vel_vec_widg = vel_vec_widg = VelocityVectorWidget()
        vel_vec_widg.checkboxClicked.connect(self.vel_vec_chk_clicked)
        layout.addWidget(vel_vec_widg)
        layout.setAlignment(vel_vec_widg, QtCore.Qt.AlignHCenter)

        layout.addStretch()
        bot_lay = QtWidgets.QHBoxLayout()
        bot_lay.addStretch()
        self.wvel_3d_view = wvel_3d_view = gl.GLViewWidget()
        wvel_3d_view.setFixedSize(450, 450)
        bot_lay.addWidget(wvel_3d_view)
        bot_lay.addStretch()
        layout.addLayout(bot_lay)
        layout.addStretch()

    def vel_vec_chk_clicked(self):
        center = self.wvel_3d_view.opts['center']
        distance = self.wvel_3d_view.opts['distance']
        elevation = self.wvel_3d_view.opts['elevation']
        azimuth = self.wvel_3d_view.opts['azimuth']

        self.plot_prop_wvel()
        self.wvel_3d_view.setCameraPosition(pos=center, distance=distance, elevation=elevation, azimuth=azimuth)

    def pop_select_prop_cb(self):
        self.select_prop_cb.clear()
        item_txts = ['None'] + get_all_propeller_dirs()
        self.select_prop_cb.addItems(item_txts)

    def select_prop_cb_changed(self):
        if self.select_prop_cb.currentText() == 'None':
            self.prop = None
            self.wvel_3d_view.clear()
        else:
            self.prop = Propeller(self.select_prop_cb.currentText())
            self.plot_prop_wvel()

        self.selectedPropChanged.emit()

    def plot_prop_wvel(self):
        self.wvel_3d_view.clear()
        total = self.vel_vec_widg.tot_vel_chk.isChecked()
        axial = self.vel_vec_widg.ax_vel_chk.isChecked()
        tang = self.vel_vec_widg.tan_vel_chk.isChecked()
        self.prop.plot_gl3d_wvel_data(total=total, axial=axial, tangential=tang, view=self.wvel_3d_view)


class VelocityVectorWidget(PDT_GroupBox):

    checkboxClicked = QtCore.pyqtSignal()

    def __init__(self):
        super(VelocityVectorWidget, self).__init__('Velocity Vectors', width=200)

        lay = QtWidgets.QHBoxLayout()
        self.setLayout(lay)
        lay.addStretch()

        self.pt_select_lay = pt_select_lay = QtWidgets.QVBoxLayout()
        lay.addLayout(pt_select_lay)
        lay.addStretch()

        velvec_lay = QtWidgets.QVBoxLayout()
        self.tot_vel_chk = tot_vel_chk = PDT_CheckBox('Total')
        tot_vel_chk.clicked.connect(self.tot_ax_tan_chk_clicked)
        velvec_lay.addWidget(tot_vel_chk)
        self.ax_vel_chk = ax_vel_chk = PDT_CheckBox('Axial (thrust)')
        ax_vel_chk.clicked.connect(self.tot_ax_tan_chk_clicked)
        velvec_lay.addWidget(ax_vel_chk)
        self.tan_vel_chk = tan_vel_chk = PDT_CheckBox('Tangential (swirl)')
        tan_vel_chk.clicked.connect(self.tot_ax_tan_chk_clicked)
        velvec_lay.addWidget(tan_vel_chk)
        lay.addLayout(velvec_lay)
        lay.addStretch()

    def tot_ax_tan_chk_clicked(self):
        self.checkboxClicked.emit()

    def pop_pt_select_lay(self):
        pass


class PropellerSweepAddDataWidget(QtWidgets.QWidget):

    dataChanged = QtCore.pyqtSignal()

    def __init__(self, main_win: 'InterfaceMainWindow'):
        super(PropellerSweepAddDataWidget, self).__init__()
        self.main_win = main_win

        lay = QtWidgets.QVBoxLayout()
        self.setLayout(lay)
        lay.addWidget(PDT_Label('Add Data Points By Range:', font_size=14, bold=True))

        opts_lay = QtWidgets.QFormLayout()
        self.vorform_cb = vorform_cb = PDT_ComboBox(width=150)
        vorform_cb.addItems(['grad', 'pot', 'vrtx'])
        vorform_cb.setCurrentIndex(1)
        opts_lay.addRow(PDT_Label('Vortex Formulation:', font_size=12), vorform_cb)
        self.vel_rle = vel_rle = RangeLineEditWidget(box_range=[0, 1000], box_single_step=1,
                                                      default_strs=['5.0', '30.0', '5.0'], spin_double_science='double')
        opts_lay.addRow(PDT_Label('Speeds:', font_size=12), vel_rle)
        self.valid_sweep_params = ['adva', 'rpm', 'thrust', 'power', 'torque']
        self.sweep_param_cb = sweep_param_cb = PDT_ComboBox(width=150)
        sweep_param_cb.addItems(self.valid_sweep_params)
        opts_lay.addRow(PDT_Label('Sweep Param:', font_size=12), sweep_param_cb)
        self.sweep_vals_rle = sweep_vals_rle = RangeLineEditWidget(box_range=[0, np.Inf], box_single_step=1,
                                                                   default_strs=['0.1', '1.0', '0.1'],
                                                                   spin_double_science='double')
        opts_lay.addRow(PDT_Label('Sweep Values:', font_size=12), sweep_vals_rle)
        lay.addLayout(opts_lay)

        self.add_btn = add_btn = PDT_PushButton('Sweep (overwrites)', font_size=12, width=150)
        add_btn.clicked.connect(self.add_btn_clicked)
        lay.addWidget(add_btn)

    @property
    def prop(self):
        return self.main_win.prop_sweep_widg.prop

    def add_btn_clicked(self):
        min_vel, max_vel, vel_step = self.vel_rle.get_start_stop_step()
        velos = list(np.arange(min_vel, max_vel, vel_step))
        param = self.sweep_param_cb.currentText()
        min_val, max_val, val_step = self.sweep_vals_rle.get_start_stop_step()
        vals = list(np.arange(min_val, max_val, val_step))
        vor = self.vorform_cb.currentText()

        if self.prop is None:
            msgbox = QtWidgets.QMessageBox()
            msgbox.about(self, 'Error', 'Must Select a Propeller() first!')
            return

        self.prop.clear_sweep_data()
        self.thread = QtCore.QThread()
        self.prop_sweep_worker = PropellerSweepWorker(prop=self.prop, velos=velos, param2sweep=param, sweep_vals=vals,
                                                      vorform=vor)
        self.prop_sweep_worker.moveToThread(self.thread)
        self.thread.started.connect(self.prop_sweep_worker.run)
        self.prop_sweep_worker.finished.connect(self.thread.quit)
        self.prop_sweep_worker.finished.connect(self.prop_sweep_worker.deleteLater)
        self.prop_sweep_worker.finished.connect(self.on_sweep_worker_finish)
        self.thread.finished.connect(self.thread.deleteLater)
        self.prop_sweep_worker.progress.connect(self.update_sweep_worker_progress)

        self.main_win.prop_sweep_widg.exist_data_widg.setEnabled(False)
        self.main_win.prop_sweep_widg.metric_plot_widget.setEnabled(False)
        self.main_win.prop_sweep_widg.select_prop_widg.vel_vec_widg.setEnabled(False)
        self.setEnabled(False)
        self.thread.start()

    def on_sweep_worker_finish(self):
        self.main_win.prop_sweep_widg.exist_data_widg.setEnabled(True)
        self.main_win.prop_sweep_widg.metric_plot_widget.setEnabled(True)
        self.main_win.prop_sweep_widg.select_prop_widg.vel_vec_widg.setEnabled(True)
        self.setEnabled(True)
        self.main_win.prog_bar.setValue(0)
        self.dataChanged.emit()

    def update_sweep_worker_progress(self, pcnt: float, strs: list):
        if pcnt is not None and isinstance(pcnt, float):
            self.main_win.prog_bar.setValue(pcnt)
        if strs is not None and isinstance(strs, list):
            self.main_win.print(strs)


class PropellerSweepMetricPlotWidget(QtWidgets.QWidget):
    def __init__(self, main_win: 'InterfaceMainWindow'):
        self.main_win = main_win
        super(PropellerSweepMetricPlotWidget, self).__init__()
        main_lay = QtWidgets.QVBoxLayout()
        self.setLayout(main_lay)
        self.creation_panel_canvas = None

        axes_cb_lay = QtWidgets.QHBoxLayout()
        main_lay.addLayout(axes_cb_lay)
        x_txts = ['x-axis'] + VALID_OPER_PLOT_PARAMS
        y_txts = ['y-axis'] + VALID_OPER_PLOT_PARAMS
        self.axes_cb_widg = AxesComboBoxWidget(x_txts=x_txts, y_txts=y_txts, init_xtxt='rpm',
                                               init_ytxt='Efficiency')
        self.xax_cb = self.axes_cb_widg.xax_cb
        self.yax_cb = self.axes_cb_widg.yax_cb
        self.xax_cb.setFixedWidth(130)
        self.yax_cb.setFixedWidth(130)
        self.xax_cb.currentTextChanged.connect(self.update_data)
        self.yax_cb.currentTextChanged.connect(self.update_data)

        axes_cb_lay.addStretch()
        axes_cb_lay.addWidget(PDT_Label('Plot Metric:', font_size=14, bold=True))
        axes_cb_lay.addWidget(self.axes_cb_widg)
        axes_cb_lay.addStretch()

        lay1 = QtWidgets.QHBoxLayout()
        lay1.addStretch()
        lay1.addWidget(PDT_Label('families of:', font_size=12))
        self.fam_cb = fam_cb = PDT_ComboBox(width=130)
        fam_cb.addItems(['None'] + VALID_OPER_PLOT_PARAMS)
        fam_cb.currentTextChanged.connect(self.update_data)
        lay1.addWidget(fam_cb)
        lay1.addWidget(PDT_Label('iso metric:', font_size=12))
        self.iso_cb = iso_cb = PDT_ComboBox(width=130)
        iso_cb.addItems(['None'] + VALID_OPER_PLOT_PARAMS)
        iso_cb.currentTextChanged.connect(self.update_data)
        lay1.addWidget(iso_cb)
        lay1.addStretch()
        main_lay.addLayout(lay1)

        self.plot_canvas = SingleAxCanvas(self, width=4.5, height=5)
        self.axes = self.plot_canvas.axes
        main_lay.addWidget(self.plot_canvas)
        toolbar = NavigationToolbar(self.plot_canvas, self)
        main_lay.addWidget(toolbar)
        main_lay.setAlignment(toolbar, QtCore.Qt.AlignHCenter)
        main_lay.addStretch()

    @property
    def prop(self):
        return self.main_win.prop_sweep_widg.prop

    def update_data(self, *args):
        self.plot_canvas.clear_axes()

        if self.prop is not None:
            yax_txt = self.yax_cb.currentText()
            xax_txt = self.xax_cb.currentText()
            if yax_txt == 'y-axis' or xax_txt == 'x-axis':
                return
            prop = self.main_win.prop_sweep_widg.prop
            if prop is None:
                return

            fam_txt = self.fam_cb.currentText()
            if fam_txt.lower() == 'none':
                fam_txt = None

            iso_txt = self.iso_cb.currentText()
            if iso_txt.lower() == 'none':
                iso_txt = None

            # need to filter out the unchecked boxes and not plot that data
            if len(args) > 0:
                print(isinstance(args[0], dict))
                print(args[0])

            prop.oper_data.plot(x_param=xax_txt, y_param=yax_txt, family_param=fam_txt, iso_param=iso_txt,
                                fig=self.plot_canvas.figure)

        self.plot_canvas.draw()


class PropellerSweepWorker(QtCore.QObject):

    progress = QtCore.pyqtSignal(object, object)
    finished = QtCore.pyqtSignal()

    def __init__(self, prop: Propeller, velos: list, param2sweep: str, sweep_vals: list, vorform: str):
        super(PropellerSweepWorker, self).__init__()
        self.prop = prop
        self.velos = velos
        self.param2sweep = param2sweep
        self.sweep_vals = sweep_vals
        self.vorform = vorform

    def run(self):
        self.prop.analyze_sweep(velo_vals=self.velos, sweep_param=self.param2sweep, sweep_vals=self.sweep_vals,
                                verbose=True, xrotor_verbose=False, vorform=self.vorform, prog_signal=self.progress)
        self.finished.emit()
