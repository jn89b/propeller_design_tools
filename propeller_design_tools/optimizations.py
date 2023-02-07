import shutil
import os
import numpy as np
import matplotlib.pyplot as plt
import pyqtgraph as pg
from pyqtgraph import opengl as gl
from propeller_design_tools import Propeller
from propeller_design_tools.user_io import Error
from propeller_design_tools.funcs import create_propeller, get_prop_db
from propeller_design_tools.user_io import Info, Warning
from propeller_design_tools.custom_opengl_classes import Custom3DAxis


class VehicleRangeOptimization:
    def __init__(self):
        pass


class VehicleDurationOptimization:
    def __init__(self):
        pass


class DutyCycleDesignOptimization:
    """Optimizes a given Propeller() design by making adjustments to design parameters (CL and either rpm or adv)
    and finding a configuration that minimizes energy used across the input duty cycle"""
    def __init__(self, base_prop: Propeller, verbose: bool = True):
        self.base_prop = base_prop
        self.save_dir = os.path.join(self.base_prop.save_folder, 'optimization')
        self.propellers = {}
        self.duty_cycle_points = []
        self.var2 = None

        # need to attempt to load any existing results here
        if os.path.exists(self.save_dir):
            prop_fpaths = [os.path.join(self.save_dir, f) for f in os.listdir(self.save_dir) if
                           os.path.isdir(os.path.join(self.save_dir, f))]
            if verbose:
                Info('Detected existing optimization results for "{}", attempting to load them ({})...'
                     .format(self.base_prop.name, len(prop_fpaths)))
            for fpath in prop_fpaths:
                prop = Propeller(fpath, verbose=False)
                name = os.path.split(fpath)[1]
                vel, cl, val2 = name.split('_', 2)
                vel = float(vel.replace('vel-', ''))
                cl = float(cl.replace('cl-', ''))
                var2, val2 = val2.split('-')
                val2 = float(val2)
                self.var2 = 'design_{}'.format(var2)
                self.propellers[(vel, cl, val2)] = prop
            if verbose:
                Info('Done!', indent_level=1)

    @property
    def var2base(self):
        return self.var2.replace('design_', '')

    @property
    def unique_vels(self):
        return list(sorted(set([key[0] for key in self.propellers])))

    @property
    def unique_cls(self):
        return list(sorted(set([key[1] for key in self.propellers])))

    @property
    def unique_var2s(self):
        return list(sorted(set([key[2] for key in self.propellers])))

    def add_duty_cycle_point(self, velocity: float = None, thrust: float = None, duration_percent: float = None,
                             duration_sec: float = None):
        point = DutyCyclePoint(velocity=velocity, thrust=thrust, duration_percent=duration_percent, duration_sec=duration_sec)
        self.duty_cycle_points.append(point)

    def create_prop_grid(self, vels: list = None, cl_consts: list = None, advs: list = None, rpms: list = None,
                         append: bool = True):
        if not append:
            # delete the optimization folder and its contents and remake it
            if os.path.exists(self.save_dir):
                shutil.rmtree(self.save_dir)

        if not os.path.exists(self.save_dir):
            os.mkdir(self.save_dir)

        # cant give both advs and rpms
        if advs is not None and rpms is not None:
            raise Error('Cannot give both "advs" and "rpms" into create_prop_grid()')

        # figure out oth sweep parameter = vel
        if vels is None:
            base_vel_val = getattr(self.base_prop, 'design_speed_mps')
            vel_sweep_vals = [v * base_vel_val for v in [0.7, 0.85, 1.0, 1.15, 1.3]]
        else:
            vel_sweep_vals = vels

        # figure out 1st sweep parameter = CL
        if cl_consts is None:
            base_cl_val = getattr(self.base_prop, 'design_cl')
            if 'const' in base_cl_val:
                base_cl_val = base_cl_val['const']
            else:
                raise Error('Optimizations only currently implemented for "const" cl')
            cl_sweep_vals = [c * base_cl_val for c in [0.7, 0.85, 1.0, 1.15, 1.3]]
        else:
            cl_sweep_vals = cl_consts

        # figure out what seconds sweep parameter is and its values
        if advs is not None:
            self.var2 = 'design_adv'
            var2_sweep_vals = advs
        elif rpms is not None:
            self.var2 = 'design_rpm'
            var2_sweep_vals = rpms
        else:
            self.var2 = sweep_var2 = 'design_adv' if self.base_prop.design_adv is not None else 'design_rpm'
            base_val2 = getattr(self.base_prop, sweep_var2)  # either adv or rpm
            var2_sweep_vals = [v * base_val2 for v in [0.7, 0.85, 1.0, 1.15, 1.3]]

        # run the sweeps
        total_cnt = len(vel_sweep_vals) * len(cl_sweep_vals) * len(var2_sweep_vals)
        cnt = 0
        for v, vel in enumerate(vel_sweep_vals):
            for i, cl in enumerate(cl_sweep_vals):
                for k, val2 in enumerate(var2_sweep_vals):
                    cnt += 1
                    Info('Creating propeller # {} / {}'.format(cnt, total_cnt))
                    opt_name = 'vel-{:.2f}_cl-{:.2f}_{}-{:.3f}'.format(vel, cl, self.var2.replace('design_', ''), val2)
                    adv_rpm_kwarg = {self.var2: val2}
                    try:
                        prop = create_propeller(name=opt_name,
                                             nblades=self.base_prop.nblades,
                                             radius=self.base_prop.radius,
                                             hub_radius=self.base_prop.hub_radius,
                                             hub_wake_disp_br=self.base_prop.hub_wake_disp_br,
                                             design_speed_mps=vel,
                                             design_cl={'const': cl},
                                             design_atmo_props=self.base_prop.design_atmo_props,
                                             design_vorform=self.base_prop.design_vorform,
                                             station_params=self.base_prop.station_params,
                                             **adv_rpm_kwarg,
                                             design_thrust=self.base_prop.design_thrust,
                                             design_power=self.base_prop.design_power,
                                             n_radial=self.base_prop.n_radial,
                                             verbose=False,
                                             show_station_fit_plots=False,
                                             plot_after=False)
                        shutil.move(prop.save_folder, self.save_dir)
                        vel = float('{:.2f}'.format(vel))
                        cl = float('{:.2f}'.format(cl))
                        val2 = float('{:.3f}'.format(val2))
                        self.propellers[(vel, cl, val2)] = prop
                    except Error:
                        vel = float('{:.2f}'.format(vel))
                        cl = float('{:.2f}'.format(cl))
                        val2 = float('{:.3f}'.format(val2))
                        Warning('XROTOR did not converge for vel-{}_cl-{}_{}-{}'.format(vel, cl, self.var2base, val2))
                        hanging_folder = os.path.join(get_prop_db(), opt_name)
                        if os.path.exists(hanging_folder):
                            shutil.rmtree(hanging_folder)

    def thrust_eff(self, vel_val, cl_val, val2_val):
        prop = self.propellers[vel_val, cl_val, val2_val]
        return prop.xrotor_op_dict['thrust(N)'] / prop.xrotor_op_dict['power(W)']

    def efficiency(self, vel_val, cl_val, val2_val):
        prop = self.propellers[vel_val, cl_val, val2_val]
        return prop.xrotor_op_dict['Efficiency']

    def var1_val(self, vel_val, cl_val, val2_val):
        prop = self.propellers[vel_val, cl_val, val2_val]
        return prop.design_cl

    def var2_val(self, vel_val, cl_val, val2_val):
        prop = self.propellers[vel_val, cl_val, val2_val]
        return getattr(prop, self.var2)

    def plot_results(self, normalized: bool = True):
        pg.mkQApp()
        view = gl.GLViewWidget()
        axis = Custom3DAxis(parent=view, color=(1.0, 1.0, 1.0, 0.6))
        axis.setSize(x=1.0, y=1.0, z=1.0)
        axis.add_labels(xlbl='CL', ylbl=self.var2, zlbl='Efficiency')
        axis.add_tick_values(xticks=[0, 0.5, 1.0], yticks=[0, 0.5, 1.0], zticks=[0, 0.5, 1.0])
        view.addItem(axis)
        view.setCameraPosition(distance=3)
        view.show()

        # create three grids, add each to the view
        xgrid = gl.GLGridItem()
        xgrid.setSize(1, 1, 1)
        xgrid.setSpacing(.1, .1, .1)
        xgrid.rotate(90, 0, 1, 0)
        xgrid.translate(0, 0.5, 0.5)
        view.addItem(xgrid)

        ygrid = gl.GLGridItem()
        ygrid.setSize(1, 1, 1)
        ygrid.setSpacing(.1, .1, .1)
        ygrid.rotate(90, 1, 0, 0)
        ygrid.translate(0.5, 0, 0.5)
        view.addItem(ygrid)

        zgrid = gl.GLGridItem()
        zgrid.setSize(1, 1, 1)
        zgrid.setSpacing(.1, .1, .1)
        zgrid.translate(0.5, 0.5, 0)
        view.addItem(zgrid)

        cmap = plt.get_cmap('jet')
        for i, vel in enumerate(self.unique_vels):

            # create grid of efficiencies
            effs = np.zeros(shape=(len(self.unique_cls), len(self.unique_var2s)))
            for c, cl in enumerate(self.unique_cls):
                for v, val in enumerate(self.unique_var2s):
                    if (vel, cl, val) in self.propellers:
                        effs[c, v] = self.efficiency(vel_val=vel, cl_val=cl, val2_val=val)
                    else:
                        effs[c, v] = 0  # np.nan

            #create surface plot item
            colors = cmap((i + 1) * np.ones(shape=(len(self.unique_cls), len(self.unique_var2s))) / len(self.unique_vels))
            if normalized:
                xs = (np.array(self.unique_cls) - min(self.unique_cls)) / (max(self.unique_cls) - min(self.unique_cls))
                ys = (np.array(self.unique_var2s) - min(self.unique_var2s)) / (max(self.unique_var2s) - min(self.unique_var2s))
            else:
                xs = np.array(self.unique_cls)
                ys = np.array(self.unique_var2s)
            itm = gl.GLSurfacePlotItem(x=xs, y=ys, z=effs, colors=colors, shader='shaded')
            view.addItem(itm)


class DutyCyclePoint:
    def __init__(self, velocity: float = None, thrust: float = None, duration_percent: float = None, duration_sec: float = None):
        self.velocity = velocity
        self.thrust = thrust
        self.duration_percent = duration_percent
        self.duration_sec = duration_sec

