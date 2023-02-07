import subprocess
import numpy as np
import os
from propeller_design_tools.propeller import Propeller
from propeller_design_tools.funcs import get_all_propeller_dirs, create_propeller, get_all_airfoil_files
from propeller_design_tools.user_io import Error
from propeller_design_tools.settings import get_prop_db

try:
    from PyQt5 import QtWidgets, QtCore
    from propeller_design_tools.helper_ui_classes import SingleAxCanvas, Capturing, AxesComboBoxWidget, \
        PropellerCreationPanelCanvas, RadialStationFitParamsCanvas
    from propeller_design_tools.helper_ui_subclasses import PDT_ComboBox, PDT_Label, PDT_SpinBox, PDT_DoubleSpinBox, \
        PDT_PushButton, PDT_LineEdit, PDT_CheckBox
    import pyqtgraph.opengl as gl
except:
    pass


class PropellerCreationWidget(QtWidgets.QWidget):
    def __init__(self, main_win: 'InterfaceMainWindow'):
        self.prop = None
        self.main_win = main_win

        super(PropellerCreationWidget, self).__init__()

        main_lay = QtWidgets.QHBoxLayout()
        self.setLayout(main_lay)
        self.control_widg = PropellerCreationControlWidget(main_win=main_win)
        main_lay.addWidget(self.control_widg)

        self.plot3d_widg = Propeller3dPlotWidget(main_win=main_win)
        self.plot3d_widg.enable_edit_chk.clicked.connect(self.enable_edit_clicked)
        main_lay.addWidget(self.plot3d_widg)

        # connecting signals
        self.plot3d_widg.select_prop_cb.currentTextChanged.connect(self.select_prop_cb_changed)

    def enable_edit_clicked(self):
        if self.plot3d_widg.select_prop_cb.currentText().lower() == 'none':
            return

        if self.plot3d_widg.enable_edit_chk.isChecked():
            self.control_widg.set_enable(True)
        else:
            self.control_widg.set_enable(False)

    def select_prop_cb_changed(self):
        self.plot3d_widg.enable_edit_chk.setChecked(False)
        self.plot3d_widg.clear_plot()
        curr_txt = self.plot3d_widg.select_prop_cb.currentText()
        if curr_txt == 'None':
            self.prop = None
            self.plot3d_widg.enable_edit_chk.setEnabled(False)
            self.control_widg.set_inputs_to_default()
            self.control_widg.set_enable(True)
            self.control_widg.save_stl_btn.setEnabled(False)
            self.control_widg.show_stl_btn.setEnabled(False)
            self.control_widg.show_blade_profs_btn.setEnabled(False)
        else:
            with Capturing() as output:
                self.prop = Propeller(name=curr_txt)
            self.plot3d_widg.enable_edit_chk.setEnabled(True)
            self.control_widg.pop_inputs_from_prop()
            self.main_win.console_te.append('\n'.join(output) if len(output) > 0 else '')
            self.plot3d_widg.update_plot(self.prop)
            self.main_win.print('XROTOR OUTPUT:')
            self.main_win.print(self.prop.get_xrotor_output_text(), fontfamily='consolas')
            self.control_widg.set_enable(False)
            self.control_widg.save_stl_btn.setEnabled(True)
            self.control_widg.show_stl_btn.setEnabled(True)
            self.control_widg.show_blade_profs_btn.setEnabled(True)


class PropellerCreationControlWidget(QtWidgets.QWidget):
    def __init__(self, main_win: 'InterfaceMainWindow'):
        super(PropellerCreationControlWidget, self).__init__()
        self.main_win = main_win
        self.widgets_to_toggle = []
        self.stl_view = None

        main_lay = QtWidgets.QHBoxLayout()
        self.setLayout(main_lay)

        form_lay2a = QtWidgets.QFormLayout()
        form_lay2c = QtWidgets.QFormLayout()

        main_lay.addStretch()
        left_vlayout = QtWidgets.QVBoxLayout()
        left_vlayout.addStretch()
        left_vlayout.addLayout(form_lay2a)
        left_vlayout.addStretch()
        main_lay.addLayout(left_vlayout)
        main_lay.addStretch()
        center_vlayout = QtWidgets.QVBoxLayout()
        center_vlayout.addStretch()
        center_vlayout.addLayout(form_lay2c)
        center_vlayout.addStretch()
        main_lay.addLayout(center_vlayout)
        main_lay.addStretch()

        # standard formlayout inputs, left form
        form_lay2a.addRow(PDT_Label('Design Point\nXROTOR Inputs', font_size=14, bold=True))
        self.name_le = PDT_LineEdit(font_size=12, width=220)
        form_lay2a.addRow(PDT_Label('Name:', font_size=12), self.name_le)
        self.nblades_sb = PDT_SpinBox(font_size=12, width=80)
        self.nblades_sb.setMinimum(1)
        self.nblades_sb.setMaximum(9)
        form_lay2a.addRow(PDT_Label('nblades:', font_size=12), self.nblades_sb)
        self.radius_sb = PDT_DoubleSpinBox(font_size=12, width=80)
        self.radius_sb.setSingleStep(0.01)
        form_lay2a.addRow(PDT_Label('Radius:', font_size=12), self.radius_sb)
        self.hub_radius_sb = PDT_DoubleSpinBox(font_size=12, width=80)
        self.hub_radius_sb.setSingleStep(0.01)
        form_lay2a.addRow(PDT_Label('Hub Radius:', font_size=12), self.hub_radius_sb)
        self.hub_wake_disp_br_sb = PDT_DoubleSpinBox(font_size=12, width=80)
        self.hub_wake_disp_br_sb.setSingleStep(0.01)
        form_lay2a.addRow(PDT_Label('Hub Wake\nDisplacement\nBody Radius:', font_size=12), self.hub_wake_disp_br_sb)
        form_lay2a.setAlignment(self.hub_wake_disp_br_sb, QtCore.Qt.AlignBottom)
        self.vorform_cb = PDT_ComboBox(font_size=12, width=100)
        self.vorform_cb.addItems(['grad', 'pot', 'vrtx'])
        form_lay2a.addRow(PDT_Label('Vortex\nFormulation:', font_size=12), self.vorform_cb)
        form_lay2a.setAlignment(self.vorform_cb, QtCore.Qt.AlignBottom)
        self.nradial_sb = PDT_SpinBox(font_size=12, width=80)
        self.nradial_sb.setMinimum(20)
        self.radius_sb.setMaximum(250)
        form_lay2a.addRow(PDT_Label('# Radial Vortex Stations: ', font_size=12), self.nradial_sb)
        self.design_speed_sb = PDT_DoubleSpinBox(font_size=12, width=80)
        form_lay2a.addRow(PDT_Label('Speed:', font_size=12), self.design_speed_sb)
        form_lay2a.addRow(PDT_Label(''))
        self.design_adv_sb = PDT_DoubleSpinBox(font_size=12, width=80)
        self.design_adv_sb.setSingleStep(0.01)
        self.design_adv_sb.setSpecialValueText('None')
        self.design_adv_sb.valueChanged.connect(self.des_adv_sb_changed)
        form_lay2a.addRow(PDT_Label('Adv:', font_size=12), self.design_adv_sb)
        form_lay2a.addRow(PDT_Label('- or -', font_size=10, italic=True))
        self.design_rpm_sb = PDT_DoubleSpinBox(font_size=12, width=80)
        self.design_rpm_sb.setSingleStep(100)
        self.design_rpm_sb.setMaximum(np.inf)
        self.design_rpm_sb.setSpecialValueText('None')
        self.design_rpm_sb.valueChanged.connect(self.des_rpm_sb_changed)
        form_lay2a.addRow(PDT_Label('RPM:', font_size=12), self.design_rpm_sb)
        form_lay2a.addRow(PDT_Label(''))

        self.design_thrust_sb = PDT_DoubleSpinBox(font_size=12, width=80)
        self.design_thrust_sb.setMaximum(np.inf)
        self.design_thrust_sb.setSpecialValueText('None')
        self.design_thrust_sb.valueChanged.connect(self.des_thrust_sb_changed)
        form_lay2a.addRow(PDT_Label('Thrust:', font_size=12), self.design_thrust_sb)
        form_lay2a.addRow(PDT_Label('- or -', font_size=10, italic=True))
        self.design_power_sb = PDT_DoubleSpinBox(font_size=12, width=80)
        self.design_power_sb.setSpecialValueText('None')
        self.design_power_sb.setMaximum(np.inf)
        self.design_power_sb.valueChanged.connect(self.des_power_sb_changed)
        form_lay2a.addRow(PDT_Label('Power:', font_size=12), self.design_power_sb)

        # center / right form layout
        self.design_cl_le = PDT_LineEdit(font_size=12, width=80)
        form_lay2c.addRow(PDT_Label('C_l (const or root, tip):', font_size=12), self.design_cl_le)

        # atmo props, vorform, station params
        self.atmo_props_widg = AtmoPropsInputWidget()
        form_lay2c.addRow(PDT_Label('Atmosphere\nProperties->', font_size=12), self.atmo_props_widg)
        self.station_params_widg = StationParamsWidget()
        form_lay2c.addRow(PDT_Label('Control\nStations->', font_size=12), self.station_params_widg)

        # extra geo params
        form_lay2c.addRow(PDT_Label('Extra Geometry Output Parameters', font_size=14, bold=True))
        self.skew_sb = PDT_DoubleSpinBox(font_size=12, width=80)
        self.skew_sb.setMaximum(45)
        form_lay2c.addRow(PDT_Label('Skew:', font_size=12), self.skew_sb)
        self.n_prof_pts_sb = PDT_SpinBox(font_size=12, width=80)
        self.n_prof_pts_sb.setSpecialValueText('None')
        form_lay2c.addRow(PDT_Label('# Profile Pts:', font_size=12), self.n_prof_pts_sb)
        self.n_profs_sb = PDT_SpinBox(font_size=12, width=80, box_range=[0, 500])
        form_lay2c.addRow(PDT_Label('# Radial Profiles:', font_size=12), self.n_profs_sb)

        # create and reset buttons
        self.create_btn = PDT_PushButton('Create!', width=150, height=40, font_size=14, bold=True)
        self.create_btn.clicked.connect(self.create_btn_clicked)
        self.reset_btn = PDT_PushButton('Reset', width=150, height=40, font_size=14, bold=True)
        self.reset_btn.clicked.connect(self.set_inputs_to_default)
        self.save_new_btn = PDT_PushButton('Save as New', width=150, height=40, font_size=14, bold=True)
        self.save_new_btn.clicked.connect(self.save_new_btn_clicked)
        self.save_new_btn.setEnabled(False)
        temp_lay = QtWidgets.QHBoxLayout()
        temp_lay.addWidget(self.create_btn)
        temp_lay.addWidget(self.reset_btn)
        temp_lay.addWidget(self.save_new_btn)
        form_lay2c.addRow(temp_lay)

        # Other geo buttons
        self.save_stl_btn = save_stl_btn = PDT_PushButton('Generate STL\nGeom. File', width=160, height=50, font_size=12)
        self.show_stl_btn = show_stl_btn = PDT_PushButton('Show STL\nGeom. File', width=140, height=50, font_size=12)
        self.show_blade_profs_btn = show_blade_profs_btn = PDT_PushButton('Show Blade xyz\nProfiles in Explorer', width=200,
                                                                          height=50, font_size=12)
        save_stl_btn.setEnabled(False)
        show_stl_btn.setEnabled(False)
        show_blade_profs_btn.setEnabled(False)
        save_stl_btn.clicked.connect(self.save_stl_btn_clicked)
        show_stl_btn.clicked.connect(self.show_stl_btn_clicked)
        show_blade_profs_btn.clicked.connect(self.show_blade_profs_btn_clicked)
        temp_lay2 = QtWidgets.QHBoxLayout()
        temp_lay2.addWidget(save_stl_btn)
        temp_lay2.addWidget(show_stl_btn)
        temp_lay2.addWidget(show_blade_profs_btn)
        form_lay2c.addRow(temp_lay2)

        # store a list of widgets to toggle enable on
        self.widgets_to_toggle = [self.name_le, self.nblades_sb, self.radius_sb, self.hub_radius_sb,
                                  self.hub_wake_disp_br_sb, self.vorform_cb, self.nradial_sb, self.design_speed_sb,
                                  self.design_adv_sb, self.design_rpm_sb, self.design_thrust_sb, self.design_power_sb,
                                  self.design_cl_le, self.atmo_props_widg.altitude_sb, self.atmo_props_widg.rho_sb,
                                  self.atmo_props_widg.nu_sb, self.atmo_props_widg.vsou_sb, self.station_params_widg,
                                  self.skew_sb, self.n_prof_pts_sb, self.n_profs_sb, self.create_btn, self.reset_btn,
                                  self.save_new_btn]

        # set all the inputs to default
        self.set_inputs_to_default()

    def show_stl_btn_clicked(self):
        prop = self.main_win.prop_widg.prop
        if prop is None:
            return

        if os.path.exists(prop.stl_fpath):
            self.stl_view = prop.plot_stl_mesh()

    def save_stl_btn_clicked(self):
        prop = self.main_win.prop_widg.prop
        if prop is None:
            return

        with Capturing() as output:
            prop.generate_stl_geometry(plot_after=False)
        self.main_win.print(output)

    def show_blade_profs_btn_clicked(self):
        prop = self.main_win.prop_widg.prop
        if prop is None:
            return

        if os.path.exists(prop.bld_prof_folder):
            subprocess.Popen('explorer "{}"'.format(os.path.normpath(prop.bld_prof_folder)))

    def save_new_btn_clicked(self):
        savedir, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Enter New Save Name', self.main_win.prop_db_select_widg.db_dir)
        if savedir:
            savename = os.path.split(savedir)[1]
            savedir = os.path.join(get_prop_db(), savename)

            if not os.path.exists(savedir):
                os.mkdir(savedir)

            self.main_win.prop_widg.prop.save_as_new(new_name=savename)

    def set_enable(self, enable: bool):
        for widg in self.widgets_to_toggle:
            if widg is not self.save_new_btn:
                widg.setEnabled(enable)
            else:
                widg.setEnabled(not enable)

    def des_thrust_sb_changed(self):
        if self.design_thrust_sb.value() == self.design_thrust_sb.minimum():
            self.design_power_sb.setEnabled(True)
        else:
            self.design_power_sb.setEnabled(False)

    def des_power_sb_changed(self):
        if self.design_power_sb.value() == self.design_power_sb.minimum():
            self.design_thrust_sb.setEnabled(True)
        else:
            self.design_thrust_sb.setEnabled(False)

    def des_adv_sb_changed(self):
        self.design_rpm_sb.setEnabled(self.design_adv_sb.value() == self.design_adv_sb.minimum())

    def des_rpm_sb_changed(self):
        self.design_adv_sb.setEnabled(self.design_rpm_sb.value() == self.design_rpm_sb.minimum())

    def set_inputs_to_default(self):
        self.name_le.setText('[enter a name]')
        self.nblades_sb.setValue(3)
        self.radius_sb.setValue(1.0)
        self.hub_radius_sb.setValue(0.08)
        self.hub_wake_disp_br_sb.setValue(0.08)
        self.vorform_cb.setCurrentText('pot')
        self.nradial_sb.setValue(50)

        self.design_speed_sb.setValue(30)
        self.design_adv_sb.setValue(0)
        self.design_rpm_sb.setValue(0)
        self.design_thrust_sb.setValue(0)
        self.design_power_sb.setValue(0)

        self.design_cl_le.setText('0.2, 0.2')
        self.atmo_props_widg.altitude_sb.setValue(self.atmo_props_widg.altitude_sb.minimum())
        self.atmo_props_widg.rho_sb.setValue(self.atmo_props_widg.rho_sb.minimum())
        self.atmo_props_widg.nu_sb.setValue(self.atmo_props_widg.nu_sb.minimum())
        self.atmo_props_widg.vsou_sb.setValue(self.atmo_props_widg.vsou_sb.minimum())

        self.station_params_widg.reset_to_default()
        self.skew_sb.setValue(self.skew_sb.minimum())
        self.n_prof_pts_sb.setValue(self.n_prof_pts_sb.minimum())
        self.n_profs_sb.setValue(50)

    def pop_inputs_from_prop(self):
        prop = self.main_win.prop_widg.prop
        self.name_le.setText(prop.name)
        self.nblades_sb.setValue(prop.nblades)
        self.radius_sb.setValue(prop.radius)
        self.hub_radius_sb.setValue(prop.hub_radius)
        self.hub_wake_disp_br_sb.setValue(prop.hub_wake_disp_br)
        self.vorform_cb.setCurrentText(prop.design_vorform)
        self.nradial_sb.setValue(prop.n_radial)

        self.design_speed_sb.setValue(prop.design_speed_mps)

        if prop.design_rpm is not None:
            self.design_rpm_sb.setValue(prop.design_rpm)
        else:
            self.design_rpm_sb.setValue(0)

        if prop.design_adv is not None:
            self.design_adv_sb.setValue(prop.design_adv)
        else:
            self.design_adv_sb.setValue(0)

        if prop.design_thrust is not None:
            self.design_thrust_sb.setValue(prop.design_thrust)
        else:
            self.design_thrust_sb.setValue(0)

        if prop.design_power is not None:
            self.design_power_sb.setValue(prop.design_power)
        else:
            self.design_power_sb.setValue(0)

        if len(prop.design_cl) == 1 and 'const' in prop.design_cl:
            self.design_cl_le.setText('{}'.format(prop.design_cl['const']))
        elif len(prop.design_cl) == 1 and 'file' in prop.design_cl:
            pass
        else:
            assert 'root' in prop.design_cl
            assert 'tip' in prop.design_cl
            self.design_cl_le.setText('{}, {}'.format(prop.design_cl['root'], prop.design_cl['tip']))

        if 'altitude_km' in prop.design_atmo_props:
            self.atmo_props_widg.altitude_sb.setValue(prop.design_atmo_props['altitude_km'])
        else:
            self.atmo_props_widg.altitude_sb.setValue(0)

        if 'dens' in prop.design_atmo_props:
            self.atmo_props_widg.rho_sb.setValue(prop.design_atmo_props['dens'])
        else:
            self.atmo_props_widg.rho_sb.setValue(0)

        if 'visc' in prop.design_atmo_props:
            self.atmo_props_widg.nu_sb.setValue(prop.design_atmo_props['visc'])
        else:
            self.atmo_props_widg.nu_sb.setValue(0)

        if 'vsou' in prop.design_atmo_props:
            self.atmo_props_widg.vsou_sb.setValue(prop.design_atmo_props['vsou'])
        else:
            self.atmo_props_widg.vsou_sb.setValue(0)

        self.station_params_widg.reset_to_default()
        for st_loc, foil_name in prop.station_params.items():
            if not foil_name.endswith('.dat'):
                foil_name = '{}.dat'.format(foil_name)
            foil_cb, roR_sb = self.station_params_widg.add_row()
            foil_cb.setCurrentText(foil_name)
            roR_sb.setValue(st_loc)

        self.skew_sb.setValue(prop.tot_skew)
        if prop.n_prof_pts is None:
            self.n_prof_pts_sb.setValue(self.n_prof_pts_sb.minimum())
        else:
            self.n_prof_pts_sb.setValue(prop.n_prof_pts)
        self.n_profs_sb.setValue(prop.n_profs)

    def create_btn_clicked(self):
        msgbox = QtWidgets.QMessageBox()

        name = self.name_le.text()
        if len(name.strip()) == 0:
            msgbox.about(self, 'Error', 'Invalid Name')
            return

        nblades = self.nblades_sb.value()
        radius = self.radius_sb.value()
        hub_radius = self.hub_radius_sb.value()
        hub_wk_disp_br = self.hub_wake_disp_br_sb.value()
        speed = self.design_speed_sb.value()
        adv = self.design_adv_sb.value() if self.design_adv_sb.value() != self.design_adv_sb.minimum() else None
        rpm = self.design_rpm_sb.value() if self.design_rpm_sb.value() != self.design_rpm_sb.minimum() else None
        if adv == self.design_adv_sb.minimum() and rpm == self.design_rpm_sb.minimum():
            msgbox.about(self, 'Error', 'Must give one of "adv" or "rpm"')
            return

        thrust = self.design_thrust_sb.value() if self.design_thrust_sb.value() != self.design_thrust_sb.minimum() else None
        power = self.design_power_sb.value() if self.design_power_sb.value() != self.design_power_sb.minimum() else None
        if thrust is None and power is None:
            msgbox.about(self, 'Error', 'Must give one of "thrust" or "power"')
            return

        nradial = self.nradial_sb.value()
        cl_txt = self.design_cl_le.text().strip()
        if len(cl_txt.split(',')) == 1:
            cl_dict = {'const': float(cl_txt)}
        elif len(cl_txt.split(',')) == 2:
            cl_dict = {'root': float(cl_txt.split(',')[0].strip()), 'tip': float(cl_txt.split(',')[1].strip())}
        else:
            msgbox = QtWidgets.QMessageBox()
            msgbox.about(self, 'Error', 'Only "const" and "linear" CL currently supported')
            return

        altitude = self.atmo_props_widg.altitude_sb.value()
        alt_ismin = altitude == self.atmo_props_widg.altitude_sb.minimum()
        rho = self.atmo_props_widg.rho_sb.value()
        rho_ismin = rho == self.atmo_props_widg.rho_sb.minimum()
        nu = self.atmo_props_widg.nu_sb.value()
        nu_ismin = nu == self.atmo_props_widg.nu_sb.minimum()
        vsou = self.atmo_props_widg.vsou_sb.value()
        vsou_ismin = vsou == self.atmo_props_widg.vsou_sb.minimum()
        if alt_ismin and any([rho_ismin, nu_ismin, vsou_ismin]):
            msgbox.about(self, 'Error', 'Can only / must give "altitude" or all three "rho", "nu" and "vsou"')
            return

        vorform = self.vorform_cb.currentText()
        stations_dict = self.station_params_widg.get_stations_dict()
        if stations_dict is None:
            msgbox.about(self, 'Error', 'Must give at least 1 station')
            return

        skew = self.skew_sb.value()
        n_prof_pts = self.n_prof_pts_sb.value() if self.n_prof_pts_sb.value() != self.n_prof_pts_sb.minimum() else None
        n_profs = self.n_profs_sb.value()

        if altitude is not None:
            atmo_props = {'altitude_km': altitude}
        else:
            atmo_props = {'rho': rho, 'nu': nu, 'vsou': vsou}

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_create_worker_progress)
        self.timer.start(1000)
        self.timer_cntr = 0

        self.thread = QtCore.QThread()
        self.prop_create_worker = CreatePropellerWorker(name=name,
                                                        nblades=nblades,
                                                        radius=radius,
                                                        hub_radius=hub_radius,
                                                        hub_wake_disp_br=hub_wk_disp_br,
                                                        design_speed_mps=speed,
                                                        design_cl=cl_dict,
                                                        design_atmo_props=atmo_props,
                                                        design_vorform=vorform,
                                                        station_params=stations_dict,
                                                        design_adv=adv,
                                                        design_rpm=rpm,
                                                        design_thrust=thrust,
                                                        design_power=power,
                                                        n_radial=nradial,
                                                        skew=skew,
                                                        n_prof_pts=n_prof_pts,
                                                        n_profs=n_profs)
        self.prop_create_worker.moveToThread(self.thread)
        self.thread.started.connect(self.prop_create_worker.run)
        self.prop_create_worker.finished.connect(self.thread.quit)
        self.prop_create_worker.finished.connect(self.prop_create_worker.deleteLater)
        self.prop_create_worker.finished.connect(self.on_create_worker_finish)
        self.thread.finished.connect(self.thread.deleteLater)
        self.prop_create_worker.progress.connect(self.update_create_worker_progress)

        self.main_win.prop_widg.setEnabled(False)
        self.thread.start()

    def on_create_worker_finish(self, prop, output):
        self.timer.stop()
        self.main_win.prog_bar.setValue(0)
        self.main_win.print(output)
        if prop:
            self.main_win.prop_db_select_widg.update_found_lbl()
            self.main_win.prop_widg.plot3d_widg.populate_select_prop_cb()
            self.main_win.prop_widg.plot3d_widg.select_prop_cb.setCurrentText(prop.name)
            self.main_win.prop_widg.setEnabled(True)

    def update_create_worker_progress(self):
        val = 2 if self.vorform_cb.currentText() == 'vrtx' else 33
        self.timer_cntr += val
        prog_val = self.timer_cntr if self.timer_cntr < 100 else 99
        self.main_win.prog_bar.setValue(prog_val)


class Propeller3dPlotWidget(QtWidgets.QWidget):
    def __init__(self, main_win: 'InterfaceMainWindow'):
        self.main_win = main_win
        super(Propeller3dPlotWidget, self).__init__()
        main_lay = QtWidgets.QVBoxLayout()
        self.setLayout(main_lay)

        form_lay = QtWidgets.QFormLayout()
        hlay = QtWidgets.QHBoxLayout()
        hlay.addLayout(form_lay)
        self.select_prop_cb = PDT_ComboBox(width=150)
        form_lay.addRow(PDT_Label('Select Propeller:', font_size=14, bold=True), self.select_prop_cb)
        self.enable_edit_chk = PDT_CheckBox('Enable Editing of Design Point', italic=True, font_size=10)
        # self.enable_edit_chk.clicked.connect(self.enable_edit_chk_clicked)
        form_lay.addRow(self.enable_edit_chk)
        self.show_rstation_btn = PDT_PushButton('Show Radial\nStation Params', font_size=14, width=160, bold=True)
        self.show_rstation_btn.clicked.connect(self.show_rstation_btn_clicked)
        hlay.addWidget(self.show_rstation_btn)
        self.show_panel_btn = PDT_PushButton('Show Design\nPoint Panel', font_size=14, width=160, bold=True)
        self.show_panel_btn.clicked.connect(self.show_panel_btn_clicked)
        hlay.addWidget(self.show_panel_btn)
        main_lay.addLayout(hlay)
        self.populate_select_prop_cb()

        self.plot_canvas = SingleAxCanvas(self, width=6, height=6, projection='3d')
        self.axes3d = self.plot_canvas.axes
        main_lay.addWidget(self.plot_canvas)

    # def enable_edit_chk_clicked(self):
    #     pass

    def show_rstation_btn_clicked(self):
        prop = self.main_win.prop_widg.prop
        if prop is not None:
            self.station_widgs = []
            for st in prop.stations:
                st_widg = QtWidgets.QWidget()
                self.station_widgs.append(st_widg)
                lay = QtWidgets.QVBoxLayout()
                st_widg.setLayout(lay)

                fit_canvas = RadialStationFitParamsCanvas()
                lay.addWidget(fit_canvas)
                st.plot_xrotor_fit_params(fig=fit_canvas.figure)

                st_widg.show()
                fit_canvas.draw()
        return

    def show_panel_btn_clicked(self):
        prop = self.main_win.prop_widg.prop
        if prop is not None:
            self.creation_panel_widg = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout()
            self.creation_panel_widg.setLayout(lay)

            self.creation_panel_canvas = PropellerCreationPanelCanvas()
            lay.addWidget(self.creation_panel_canvas)
            prop.plot_design_point_panel(fig=self.creation_panel_canvas.figure)

            self.creation_panel_widg.show()
            self.creation_panel_canvas.draw()

    def update_plot(self, prop: Propeller):
        with Capturing() as output:
            prop.plot_mpl3d_geometry(interp_profiles=True, hub=True, input_stations=True, chords_betas=True, LE=True,
                                     TE=True, fig=self.plot_canvas.figure)
        self.main_win.console_te.append('\n'.join(output) if len(output) > 0 else '')
        self.plot_canvas.draw()

    def clear_plot(self):
        self.axes3d.clear()
        self.plot_canvas.draw()

    def populate_select_prop_cb(self):
        self.select_prop_cb.blockSignals(True)
        self.select_prop_cb.clear()
        self.select_prop_cb.blockSignals(False)
        self.select_prop_cb.addItems(['None'] + get_all_propeller_dirs())


class StationParamsWidget(QtWidgets.QWidget):
    def __init__(self):
        super(StationParamsWidget, self).__init__()

        main_lay = QtWidgets.QVBoxLayout()
        self.rows_lay = QtWidgets.QFormLayout()
        self.setLayout(main_lay)
        main_lay.addLayout(self.rows_lay)

        self.header_row_strs = ['#', 'Foil', 'r/R']
        self.add_header_row()
        self.add_btn = PDT_PushButton('(+) add', width=80, font_size=11)
        self.remove_btn = PDT_PushButton('(-) remove', width=100, font_size=11)

        btn_lay = QtWidgets.QHBoxLayout()
        btn_lay.addWidget(self.add_btn)
        btn_lay.addWidget(self.remove_btn)
        main_lay.addLayout(btn_lay)

        # connect signals
        self.add_btn.clicked.connect(self.add_row)
        self.remove_btn.clicked.connect(self.remove_row)

    def reset_to_default(self):
        count = self.rows_lay.rowCount()
        while count > 1:
            self.rows_lay.removeRow(count - 1)
            count -= 1

    def add_header_row(self):
        num_lbl = PDT_Label(self.header_row_strs[0], font_size=11)
        foil_lbl = PDT_Label(self.header_row_strs[1], font_size=11)
        roR_lbl = PDT_Label(self.header_row_strs[2], font_size=11)
        rt_lay = QtWidgets.QHBoxLayout()
        rt_lay.addWidget(foil_lbl)
        rt_lay.addWidget(roR_lbl)
        rt_widg = QtWidgets.QWidget()
        rt_widg.setLayout(rt_lay)
        self.rows_lay.addRow(num_lbl, rt_widg)

    def add_row(self):
        rt_lay = QtWidgets.QHBoxLayout()
        rt_widg = QtWidgets.QWidget()
        rt_widg.setLayout(rt_lay)
        if self.rows_lay.rowCount() > 1:
            msgbox = QtWidgets.QMessageBox()
            msgbox.about(self, 'Error', '> 1 station not yet implemented in PDT')
            return
        num_lbl = PDT_Label('{}'.format(self.rows_lay.rowCount()), font_size=11)
        foil_cb = PDT_ComboBox(font_size=11, width=140)
        foil_cb.addItems(get_all_airfoil_files())
        roR_sb = PDT_DoubleSpinBox(font_size=11)
        roR_sb.setMaximum(1.0)
        roR_sb.setSingleStep(0.01)
        roR_sb.setValue(0.75)
        rt_lay.addWidget(foil_cb)
        rt_lay.addWidget(roR_sb)
        self.rows_lay.addRow(num_lbl, rt_widg)
        return foil_cb, roR_sb

    def remove_row(self):
        row = self.rows_lay.rowCount() - 1
        self.rows_lay.removeRow(row)

    def get_stations_dict(self):
        if self.rows_lay.rowCount() == 1:
            return None
        else:
            stations = {}
            for row in range(1, self.rows_lay.rowCount()):
                rt_widg = self.rows_lay.itemAt(row, 1).widget()
                itm1, itm2 = [rt_widg.layout().itemAt(i) for i in range(rt_widg.layout().count())]
                foil_cb = itm1.widget()
                roR_sb = itm2.widget()
                stations[roR_sb.value()] = foil_cb.currentText()
        return stations


class AtmoPropsInputWidget(QtWidgets.QWidget):
    def __init__(self):
        super(AtmoPropsInputWidget, self).__init__()
        lay = QtWidgets.QHBoxLayout()
        self.setLayout(lay)
        left_lay = QtWidgets.QVBoxLayout()
        left_center_lay = QtWidgets.QFormLayout()
        left_lay.addStretch()
        left_lay.addLayout(left_center_lay)
        left_lay.addStretch()
        right_lay = QtWidgets.QFormLayout()
        lay.addLayout(left_lay)
        lay.addWidget(PDT_Label('or'))
        lay.addLayout(right_lay)
        lay.addStretch()

        self.altitude_sb = PDT_DoubleSpinBox(width=80, font_size=12)
        self.altitude_sb.setMinimum(-2)
        self.altitude_sb.setSpecialValueText('None')
        left_center_lay.addRow(PDT_Label('Altitude:', font_size=12), self.altitude_sb)

        self.rho_sb = PDT_DoubleSpinBox(width=80, font_size=12)
        self.rho_sb.setSpecialValueText('None')
        right_lay.addRow(PDT_Label('Rho:', font_size=12), self.rho_sb)
        self.nu_sb = PDT_DoubleSpinBox(width=80, font_size=12)
        self.nu_sb.setSpecialValueText('None')
        right_lay.addRow(PDT_Label('Nu:', font_size=12), self.nu_sb)
        self.vsou_sb = PDT_DoubleSpinBox(width=80, font_size=12)
        self.vsou_sb.setSpecialValueText('None')
        right_lay.addRow(PDT_Label('Vsou:', font_size=12), self.vsou_sb)

        # connect some signals
        self.altitude_sb.valueChanged.connect(self.altitude_sb_changed)
        self.rho_sb.valueChanged.connect(self.rho_sb_changed)
        self.nu_sb.valueChanged.connect(self.nu_sb_changed)
        self.vsou_sb.valueChanged.connect(self.vsou_sb_changed)

    def vsou_sb_changed(self):
        if self.rho_sb.value() == self.rho_sb.minimum() \
                and self.nu_sb.value() == self.nu_sb.minimum() \
                and self.vsou_sb.value() == self.vsou_sb.minimum():
            self.altitude_sb.setEnabled(True)
        else:
            self.altitude_sb.setEnabled(False)

    def nu_sb_changed(self):
        if self.rho_sb.value() == self.rho_sb.minimum() \
                and self.nu_sb.value() == self.nu_sb.minimum() \
                and self.vsou_sb.value() == self.vsou_sb.minimum():
            self.altitude_sb.setEnabled(True)
        else:
            self.altitude_sb.setEnabled(False)

    def rho_sb_changed(self):
        if self.rho_sb.value() == self.rho_sb.minimum() \
                and self.nu_sb.value() == self.nu_sb.minimum() \
                and self.vsou_sb.value() == self.vsou_sb.minimum():
            self.altitude_sb.setEnabled(True)
        else:
            self.altitude_sb.setEnabled(False)

    def altitude_sb_changed(self):
        if self.altitude_sb.value() == self.altitude_sb.minimum():
            self.rho_sb.setEnabled(True)
            self.nu_sb.setEnabled(True)
            self.vsou_sb.setEnabled(True)
        else:
            self.rho_sb.setEnabled(False)
            self.nu_sb.setEnabled(False)
            self.vsou_sb.setEnabled(False)


class CreatePropellerWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal(object, list)
    progress = QtCore.pyqtSignal(int)

    def __init__(self, name: str, nblades: int, radius: float, hub_radius: float, hub_wake_disp_br: float,
                 design_speed_mps: float, design_cl: dict, design_atmo_props: dict, design_vorform: str,
                 station_params: dict = None, design_adv: float = None, design_rpm: float = None,
                 design_thrust: float = None, design_power: float = None, n_radial: int = 50, skew: float = 0.0,
                 n_prof_pts: int = None, n_profs: int = 50):

        super(CreatePropellerWorker, self).__init__()

        self.name = name
        self.nblades = nblades
        self.radius = radius
        self.hub_radius = hub_radius
        self.hub_wake_disp_br = hub_wake_disp_br
        self.design_speed_mps = design_speed_mps
        self.design_cl = design_cl
        self.design_atmo_props = design_atmo_props
        self.design_vorform = design_vorform
        self.station_params = station_params
        self.design_adv = design_adv
        self.design_rpm = design_rpm
        self.design_thrust = design_thrust
        self.design_power = design_power
        self.n_radial = n_radial
        self.skew = skew
        self.n_prof_pts = n_prof_pts
        self.n_profs = n_profs

    def run(self):
        try:
            with Capturing() as output:
                prop = create_propeller(name=self.name,
                                        nblades=self.nblades,
                                        radius=self.radius,
                                        hub_radius=self.hub_radius,
                                        hub_wake_disp_br=self.hub_wake_disp_br,
                                        design_speed_mps=self.design_speed_mps,
                                        design_cl=self.design_cl,
                                        design_atmo_props=self.design_atmo_props,
                                        design_vorform=self.design_vorform,
                                        station_params=self.station_params,
                                        design_adv=self.design_adv,
                                        design_rpm=self.design_rpm,
                                        design_thrust=self.design_thrust,
                                        design_power=self.design_power,
                                        n_radial=self.n_radial,
                                        verbose=True,
                                        show_station_fit_plots=False,
                                        plot_after=False,
                                        tmout=None,
                                        hide_windows=True,
                                        geo_params={'tot_skew': self.skew, 'n_prof_pts': self.n_prof_pts,
                                                    'n_profs': self.n_profs})
        except Exception as e:
            prop = None
            output = [e.__repr__()]

        self.finished.emit(prop, output)
