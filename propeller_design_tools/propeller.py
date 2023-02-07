import os
import shutil
from propeller_design_tools import funcs
from propeller_design_tools.user_io import Info, Error, Warning
from propeller_design_tools.settings import get_setting
from propeller_design_tools.airfoil import Airfoil
from propeller_design_tools.settings import VALID_OPER_PLOT_PARAMS
from propeller_design_tools.custom_opengl_classes import Custom3DArrow
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from mpl_toolkits import mplot3d
import numpy as np
from stl import mesh
from typing import Union
import pyqtgraph as pg
import pyqtgraph.opengl as gl


class Propeller(object):

    creation_attrs = {'nblades': int, 'radius': float, 'hub_radius': float, 'hub_wake_disp_br': float,
                      'design_speed_mps': float, 'design_adv': float, 'design_rpm': float, 'design_thrust': float,
                      'design_power': float, 'design_cl': dict, 'design_atmo_props': dict, 'design_vorform': str,
                      'station_params': dict, 'station_polars': list, 'geo_params': dict}
    saveload_attrs = {**creation_attrs, **{'name': str, 'meta_file': str, 'xrr_file': str, 'xrop_file': str,
                                           'blade_data': dict, 'blade_xyz_profiles': dict}}

    def __init__(self, name, verbose: bool = True, **kwargs):
        # name is always given, detect if it's a filepath
        self.savepath = None
        if os.path.exists(name):
            self.savepath, name = os.path.split(name)
        self.name = name.replace('.txt', '')
        self.oper_data = None
        self.wvel_data = None
        self.stl_mesh = None

        # check if the prop db exists
        prop_db = get_setting('propeller_database')
        if prop_db is None:
            raise Error(s='No Propeller Database is set!  First set one with "pdt.set_propeller_database(str)".')

        # initialize all attrs to None for script auto-completion detection
        self.nblades, self.radius, self.hub_radius, self.hub_wake_disp_br, self.design_speed_mps, self.design_adv, \
        self.design_rpm, self.design_thrust, self.design_power, self.design_cl, self.design_atmo_props, \
        self.design_vorform, self.station_params, self.geo_params, self.xrotor_d, self.xrotor_op_dict, \
        self.blade_data, self.blade_xyz_profiles = [None] * 18

        # if no kwargs were given and there's a meta_file, load it
        if len(kwargs) == 0:
            if os.path.exists(self.meta_file):
                if verbose:
                    Info(s='Loading propeller "meta-file" ({})'.format(self.meta_file))
                self.load_from_savefile(verbose=verbose)
            else:
                raise FileNotFoundError('Could not find file {}'.format(self.meta_file))
        else:  # cycle thru kwargs and set if they're valid, if not ignore them
            for key, val in kwargs.items():
                if key in self.creation_attrs:
                    setattr(self, key, val)
                else:
                    raise Error('Unknown KWARG input "{}"'.format(key))

        # attempt to load any oper sweep data and any wvel sweep data
        self.oper_data = PropellerOperData(directory=self.oper_data_dir)
        self.oper_data.load_oper_sweep_results(verbose=verbose)
        self.wvel_data = PropellerWVelData(directory=self.wvel_data_dir)
        self.wvel_data.load_wvel_sweep_results(verbose=verbose)

        # attempt to load any STL mesh data
        self.load_stl_geometry(verbose=verbose)

    @property
    def stl_fpath(self):
        return os.path.join(self.save_folder, '{}.stl'.format(self.name))

    @property
    def station_polar_folder(self):
        return os.path.join(self.save_folder, 'station_polars')

    @property
    def bld_prof_folder(self):
        return os.path.join(self.save_folder, 'blade_profiles')

    @property
    def xrr_file(self):
        return os.path.join(self.save_folder, '{}.xrr'.format(self.name))

    @property
    def xrop_file(self):
        return os.path.join(self.save_folder, '{}.xrop'.format(self.name))

    @property
    def meta_file(self):
        return os.path.join(self.save_folder, '{}.meta'.format(self.name))

    @property
    def save_folder(self):
        if self.savepath is None:
            return os.path.join(get_setting('propeller_database'), self.name)
        else:
            return os.path.join(self.savepath, self.name)

    @property
    def tot_skew(self):
        return self.geo_params['tot_skew']

    @property
    def n_prof_pts(self):
        return self.geo_params['n_prof_pts']

    @property
    def n_profs(self):
        return self.geo_params['n_profs']

    @property
    def design_rho(self):
        if 'dens' in self.design_atmo_props:
            return self.design_atmo_props['dens']

    @design_rho.setter
    def design_rho(self, value):
        self.design_atmo_props['dens'] = value

    @property
    def disk_area_m_sqrd(self):
        if self.radius is not None and self.hub_radius is not None:
            return np.pi * (self.radius ** 2 - self.hub_radius ** 2)

    @property
    def ideal_eff(self):
        req_attrs = [self.design_thrust, self.design_rho, self.disk_area_m_sqrd, self.design_speed_mps]
        if all([attr is not None for attr in req_attrs]):
            return funcs.calc_ideal_eff(*req_attrs)

    @property
    def disk_loading(self):
        if self.xrotor_op_dict is not None and self.disk_area_m_sqrd is not None:
            return self.xrotor_op_dict['thrust(N)'] / self.disk_area_m_sqrd

    @property
    def oper_data_dir(self):
        return os.path.join(os.path.split(self.meta_file)[0], 'oper_data')

    @property
    def wvel_data_dir(self):
        return os.path.join(os.path.split(self.meta_file)[0], 'wvel_data')

    @property
    def n_radial(self):
        return len(self.blade_xyz_profiles)

    @property
    def valid_oper_plot_params(self):
        return

    def save_as_new(self, new_name: str):
        # store filepaths before we change name
        old_xrop_file = self.xrop_file * 1
        old_xrr_file = self.xrr_file * 1
        old_blade_profs_folder = self.bld_prof_folder * 1

        # change the name, make a new directory
        self.name = new_name
        if not os.path.exists(self.save_folder):
            os.mkdir(self.save_folder)

        # save off a new meta file, copy the xrop and xrr files
        self.save_meta_file()
        shutil.copyfile(old_xrop_file, self.xrop_file)
        shutil.copyfile(old_xrr_file, self.xrr_file)

        # blade profiles
        if not os.path.exists(self.bld_prof_folder):
            os.mkdir(self.bld_prof_folder)
        for fname in [f for f in os.listdir(old_blade_profs_folder) if f.endswith('.txt')]:
            fpath = os.path.join(old_blade_profs_folder, fname)
            copypath = os.path.join(self.bld_prof_folder, fname)
            shutil.copyfile(fpath, copypath)

    def read_pdt_metafile(self):
        # read in the PDT meta-file (in the root propeller database) and set Propeller attrs
        with open(self.meta_file, 'r') as f:
            txt = f.read().strip()
        lines = txt.split('\n')

        blade_data = {}
        point_cloud = {}

        for line in lines:
            line_attr, line_val = [i.strip() for i in line.split(':', 1)]
            if 'blade_data_' in line_attr:
                blade_data[line_attr.split('blade_data_', 1)[1]] = np.array([float(v) for v in line_val.strip().split(', ')])
            if 'point_cloud_' in line_attr:
                point_cloud[line_attr.split('point_cloud_', 1)[1]] = np.array([float(v) for v in line_val.strip().split(', ')])
            for attr, tipe in self.saveload_attrs.items():
                if line_attr == attr:
                    val = line.split(': ', 1)[1]
                    if val == 'None':
                        val = None
                    else:
                        if tipe is int:
                            val = int(val)
                        elif tipe is float:
                            val = float(val)
                        elif tipe is dict:
                            items = [item.split(': ') for item in
                                     val.replace('{', '').replace('}', '').replace("'", '').split(', ')]
                            # check for keys that are floats or ints
                            keys_are_nums = [itm[0].replace('.', '').isnumeric() for itm in items]
                            if all(keys_are_nums):
                                for i, itm in enumerate(items):
                                    new_itm = [float(itm[0]), itm[1]]
                                    items[i] = new_itm
                            val = {}
                            for key, entry in items:
                                if 'none' == entry.lower():
                                    entry = None
                                try:    # try to convert to float
                                    val[key] = float(entry)
                                except:     # otherwise store as string
                                    val[key] = entry
                        elif tipe is list:
                            val = []
                    setattr(self, attr, val)
        self.set_blade_data(blade_dict=blade_data)

    def read_xrotor_restart(self):
        with open(self.xrr_file, 'r') as f:
            txt = f.read().strip()
        lines = txt.split('\n')

        def read_line_pair(kw_idx):
            keywords = lines[kw_idx].strip('!').split()
            values = lines[kw_idx + 1].split()
            return dict(zip(keywords, values))

        def read_xi_sect(xi_idx):
            xi_d = {}
            for lni in [xi_idx, xi_idx + 2, xi_idx + 4, xi_idx + 6, xi_idx + 8]:
                for k, v in read_line_pair(lni).items():
                    xi_d[k] = float(v)
            return xi_d

        def read_geo_stations(header_idx):
            geo_d = {}
            headers = lines[header_idx].strip('!').split()
            for h in headers:
                geo_d[h] = []
            for idx in range(header_idx + 1, len(lines)):
                vals = lines[idx].split()
                if len(vals) == len(headers):
                    for i, val in enumerate(vals):
                        geo_d[headers[i]].append(float(val))
            return geo_d

        d = {}
        design_param_lines = [2, 4, 6, 8]
        for ln_idx in design_param_lines:
            for k, v in read_line_pair(ln_idx).items():
                d[k] = float(v)

        xi_lines = [i * 10 for i in range(1, int(d['Naero']) + 1)]   # works out that each xi section is 10 lines, and 1st one on line 10 always
        for sect_idx, ln_idx in enumerate(xi_lines):
            xi_d = read_xi_sect(ln_idx)
            d['Xisection_{}'.format(sect_idx)] = xi_d

        for k, v in read_line_pair(kw_idx=xi_lines[-1] + 10).items():
            d[k] = v

        for k, v in read_line_pair(kw_idx=xi_lines[-1] + 12).items():
            d[k] = int(v)

        for k, v in read_geo_stations(header_idx=xi_lines[-1] + 14).items():
            d[k] = v

        # turn all lists into numpy arrays before returning
        for key, val in d.items():
            if isinstance(val, list):
                d[key] = np.array(val)

        return d

    def load_from_savefile(self, verbose):
        # 1st set attrs from the PDT metafile
        self.read_pdt_metafile()
        if verbose:
            Info(s='Successfully read meta-file (.meta)!', indent_level=1)

        # set the stations... why did I do it this way??
        self.set_stations(plot_also=False, verbose=verbose, from_loadsave_file=True)
        if verbose:
            Info(s='Successfully read and set station polars!', indent_level=1)

        # then read in the XROTOR restart file (in the xrotor_geometry_files)
        self.xrotor_d = self.read_xrotor_restart()
        if verbose:
            Info(s='Successfully read XROTOR restart file (.xrr)!', indent_level=1)

        # then read the operating point output file (in xrotor_op_files)
        self.xrotor_op_dict = funcs.read_xrotor_op_file(fpath=self.xrop_file)
        if verbose:
            Info(s='Successfully read XROTOR operating-point file (.xrop)!', indent_level=1)

        # and finally read in the point cloud files
        self.blade_xyz_profiles = {}
        fnames = funcs.search_files(folder=self.bld_prof_folder)
        for fname in fnames:
            prof_num = int(fname.replace('profile_', '').replace('.txt', ''))
            xyz_prof = funcs.read_profile_xyz(fpath=os.path.join(self.bld_prof_folder, fname))
            self.blade_xyz_profiles[prof_num] = xyz_prof
        if verbose:
            Info(s='Successfully read blade profiles!', indent_level=1)

        return

    def set_stations(self, plot_also: bool = True, verbose: bool = False, from_loadsave_file: bool = False):
        if not from_loadsave_file:
            self.stations, txt = funcs.create_radial_stations(prop=self, plot_also=plot_also, verbose=verbose)
        else:
            self.stations = funcs.read_radial_stations(prop=self, plot_also=plot_also, verbose=False)
            txt = ''
        return txt

    def show_station_fits(self):
        for st in self.stations:
            fig = st.plot_xrotor_fit_params()

    def set_blade_data(self, blade_dict: dict):
        self.blade_data = blade_dict
        return

    def save_meta_file(self):
        attrs_2_ignore = ['blade_xyz_profiles', 'meta_file', 'xrr_file', 'xrop_file', 'station_polars']   # ignore the files so that prop_dirs can be switched

        if os.path.exists(self.meta_file):
            os.remove(self.meta_file)

        with open(self.meta_file, 'w') as f:
            for attr in [a for a in self.saveload_attrs if a not in attrs_2_ignore]:
                if attr == 'blade_data':
                    for key, val in self.blade_data.items():
                        val = ', '.join([str(i) for i in val])
                        f.write('{}: {}\n'.format('blade_data_{}'.format(key), val))
                else:
                    f.write('{}: {}\n'.format(attr, getattr(self, attr)))

    def save_station_polars(self):
        if not os.path.exists(self.station_polar_folder):
            os.mkdir(self.station_polar_folder)

        for i, roR in enumerate(self.station_params.keys()):
            station = self.stations[i]
            foil_name = self.station_params[roR]
            savename = '{}_{}.polar'.format(roR, foil_name)
            savepath = os.path.join(self.station_polar_folder, savename)
            with open(savepath, 'w') as f:
                for key, val in station.foil_polar.items():
                    if isinstance(val, list) or isinstance(val, np.ndarray):
                        val = ', '.join([str(v) for v in val])
                    f.write('{}: {}\n'.format(key, val))

    def get_blade_le_te(self, rotate_deg: float = 0.0, axis_shift: float = 0.25):
        radii = self.radius * np.array(self.xrotor_d['r/R'])
        chords = self.radius * np.array(self.xrotor_d['C/R'])
        betas = np.array(self.xrotor_d['Beta0deg'])
        le_pts = []
        te_pts = []
        for radius, chord, beta in zip(radii, chords, betas):
            le_te_coords = np.array([[0.0, 1.0], [0.0, 0.0]])
            xs, ys, zs = funcs.generate_3D_profile_points(nondim_xy_coords=le_te_coords, radius=radius,
                                                            axis_shift=axis_shift, chord_len=chord, beta_deg=beta,
                                                            skew_deg=rotate_deg)
            le_pts.append([xs[0], ys[0], zs[0]])
            te_pts.append([xs[1], ys[1], zs[1]])
        return le_pts, te_pts

    def get_blade_quarter_chords(self):  # for plotting of wvel vectors
        chordlines = self.get_blade_chordlines(rotate_deg=0)
        q_chord_pts = []
        for line in chordlines:
            qtr_idx = int(len(line) / 4)
            q_chord_pts.append(line[qtr_idx])

        return q_chord_pts

    def get_blade_chordlines(self, rotate_deg: float, axis_shift: float = 0.25, npts: int = 50):
        radii = self.radius * np.array(self.xrotor_d['r/R'])
        chords = self.radius * np.array(self.xrotor_d['C/R'])
        betas = np.array(self.xrotor_d['Beta0deg'])
        chordlines = []
        for radius, chord, beta in zip(radii, chords, betas):
            xs = np.linspace(0, 1, npts)
            ys = np.zeros(len(xs))
            chordline_nondim = np.vstack([xs, ys])
            xs, ys, zs = funcs.generate_3D_profile_points(nondim_xy_coords=chordline_nondim, radius=radius,
                                                   axis_shift=axis_shift, chord_len=chord, beta_deg=beta,
                                                   skew_deg=rotate_deg)
            coords = list(zip(xs, ys, zs))
            chordlines.append(coords)
        return chordlines

    def interp_foil_profiles(self, n_prof_pts: int = None, n_profs: int = 50, tot_skew: float = 0.0):

        assert len(self.stations) > 0

        if len(self.stations) != 1:
            raise Error('> 1 profile interpolation not yet implemented')

        if tot_skew != 0.0:
            Info('Blade "skew" is not implemented in XROTOR, and therefore not reflected in XROTOR results.\n'
                 '  > Skew effects are considered negligible for PDT purposes for small enough skew angles.')

        # clear out the existing xyz profiles
        funcs.delete_files_from_folder(self.bld_prof_folder)

        station = self.stations[0]
        # nondim_coords = station.foil.get_coords(n_interp=n_prof_pts)
        nondim_coords = station.foil.get_coords_closed_te(n_interp=n_prof_pts)

        self.blade_xyz_profiles = {}
        for i, roR in enumerate(np.linspace(self.blade_data['r/R'][0], self.blade_data['r/R'][-1], n_profs)):
            chord = np.interp(x=roR, xp=self.blade_data['r/R'], fp=self.blade_data['CH']) * self.radius
            beta = np.rad2deg(np.interp(x=roR, xp=self.blade_data['r/R'], fp=self.blade_data['BE']))
            skew = tot_skew * roR
            r = roR * self.radius

            prof_xyz = funcs.generate_3D_profile_points(nondim_xy_coords=nondim_coords, radius=r, axis_shift=0.25,
                                                        chord_len=chord, beta_deg=beta, skew_deg=skew)
            self.blade_xyz_profiles[i] = prof_xyz

        # now save them all for loading later
        for key, val in self.blade_xyz_profiles.items():
            savepath = os.path.join(self.bld_prof_folder, 'profile_{}.txt'.format(key))
            xpts, ypts, zpts = val
            with open(savepath, 'w') as f:
                f.write('x, y, z\n')
                for xp, yp, zp in zip(xpts, ypts, zpts):
                    f.write('{:.6f}, {:.6f}, {:.6f}\n'.format(xp, yp, zp))

    def get_xrotor_output_text(self):
        line_num = 0
        txt = ''
        with open(self.xrop_file, 'r') as f:
            while line_num < 16:
                txt += f.readline()
                line_num += 1
        return txt

    def plot_design_point_panel(self, LE: bool = True, TE: bool = True, chords_betas: bool = True, hub: bool = True,
                                input_stations: bool = True, interp_profiles: bool = True, savefig: bool = False,
                                fig=None):
        if fig is None:
            created_from_ui = False
            radial_axes = {'': None, 'c/R': None, 'beta(deg)': None, 'CL': None, 'CD': None,
                           'thrust_eff': None, 'RE': None, 'Mach': None, 'effi': None, 'effp': None,
                           'GAM': None, 'Ttot': None, 'Ptot': None, 'VA/V': None, 'VT/V': None}
            gs = gridspec.GridSpec(nrows=10, ncols=5, figure=fig)
            fig = plt.figure(figsize=(18, 10))
            ax3d = fig.add_subplot(gs[0:7, 0:2], projection='3d')
            txt_ax = fig.add_subplot(gs[7:10, 0:2])

            for i, p in enumerate(radial_axes):
                row = i % 5
                col = int(i / 5) + 2
                if col == 2:
                    ax = fig.add_subplot(gs[2 * row:2 * row + 2, col])
                else:
                    ax = fig.add_subplot(gs[2 * row:2 * row + 2, col])
                radial_axes[p] = ax
                ax.grid(True)
                ax.set_ylabel(p)
                if row == 4:
                    ax.set_xlabel('r/R')
                if p == '':
                    ax.set_visible(False)
        else:  # fig is not None -> we were passed a Figure object from a UI class
            created_from_ui = True
            ax3d = fig.axes[0]
            txt_ax = fig.axes[1]
            radial_axes = {'': fig.axes[2], 'c/R': fig.axes[3], 'beta(deg)': fig.axes[4], 'CL': fig.axes[5], 'CD': fig.axes[6],
                           'thrust_eff': fig.axes[7], 'RE': fig.axes[8], 'Mach': fig.axes[9], 'effi': fig.axes[10], 'effp': fig.axes[11],
                           'GAM': fig.axes[12], 'Ttot': fig.axes[13], 'Ptot': fig.axes[14], 'VA/V': fig.axes[15], 'VT/V': fig.axes[16]}


        ax3d.set_xlabel('X')
        ax3d.set_ylabel('Y')
        ax3d.set_zlabel('Z')

        title_txt = 'Propeller Geometry - {}'.format(self.name)
        ax3d.set_title(title_txt)

        def do_ax3d():
            blades = np.arange(self.xrotor_d['Nblds'])
            angles = 360 / self.xrotor_d['Nblds'] * blades

            # plot le and te lines
            if LE:
                for ang in angles:
                    le_pts, te_pts = self.get_blade_le_te(rotate_deg=ang)
                    le_line, = ax3d.plot3D(xs=[pt[0] for pt in le_pts], ys=[pt[1] for pt in le_pts],
                                           zs=[pt[2] for pt in le_pts], c='k', lw=2)
            else:
                le_line = None

            if TE:
                for ang in angles:
                    le_pts, te_pts = self.get_blade_le_te(rotate_deg=ang)
                    te_line, = ax3d.plot3D(xs=[pt[0] for pt in te_pts], ys=[pt[1] for pt in te_pts],
                                           zs=[pt[2] for pt in te_pts], c='k', ls='-.', lw=2)
            else:
                te_line = None

            # plot stations
            if chords_betas:
                for ang in angles:
                    chordlines = self.get_blade_chordlines(rotate_deg=ang)
                    for line in chordlines:
                        xs, ys, zs = zip(*line)
                        station_line, = ax3d.plot3D(xs=xs, ys=ys, zs=zs, c='rosybrown', lw=1, ls='--')
            else:
                station_line = None

            # plot station_params
            if input_stations:
                radii = self.xrotor_d['r/R'] * self.radius
                chords = self.xrotor_d['C/R'] * self.radius
                betas = self.xrotor_d['Beta0deg'].copy()
                for roR, foil_name in self.station_params.items():
                    # station dimensionalized parameters
                    r = roR * self.radius
                    ch = np.interp(r, radii, chords)
                    beta = np.interp(r, radii, betas)
                    sk = self.geo_params['tot_skew'] * roR

                    # load the foil, shift, flip, and dimensionalize coordinates
                    foil = Airfoil(foil_name, verbose=False)
                    xc, yc, zc = funcs.generate_3D_profile_points(nondim_xy_coords=foil.get_coords(), radius=r,
                                                                  axis_shift=0.25, chord_len=ch, beta_deg=beta,
                                                                  skew_deg=sk)
                    foils_line, = ax3d.plot3D(xs=xc, ys=yc, zs=zc, c='red', alpha=0.7, lw=1)
            else:
                foils_line = None

            # plot interpolated profiles
            if interp_profiles:
                for prof_num, prof_xyz in self.blade_xyz_profiles.items():
                    xc, yc, zc = prof_xyz
                    prof_line, = ax3d.plot3D(xs=xc, ys=yc, zs=zc, c='maroon', lw=1, alpha=0.7)
            else:
                prof_line = None

            # plot hub
            if hub:
                hub_thickness = abs(max([pt[2] for pt in le_pts]) - min([pt[2] for pt in te_pts]))
                theta = np.linspace(0, np.pi * 2, 50)
                hub_x = np.cos(theta) * self.hub_radius
                hub_y = np.sin(theta) * self.hub_radius
                top_zs = np.ones(len(hub_x)) * hub_thickness / 2
                bot_zs = -np.ones(len(hub_x)) * hub_thickness / 2
                hub_line, = ax3d.plot3D(xs=hub_x, ys=hub_y, zs=top_zs, c='gray', lw=2)
                hub_line, = ax3d.plot3D(xs=hub_x, ys=hub_y, zs=bot_zs, c='gray', lw=2)
            else:
                hub_line = None

            # set square axes and finish up formatting stuff
            lim = (-self.radius * 0.65, self.radius * 0.65)
            ax3d.set_xlim(lim)
            ax3d.set_ylim(lim)
            ax3d.set_zlim(lim)
            leg_handles = [le_line, te_line, hub_line, foils_line, station_line, prof_line]
            leg_labels = ['L.E.', 'T.E.', 'Hub', 'Input Stations', 'XROTOR Stations', 'Interpolated Geom.']

            leg_labels = [leg_labels[n] for n in range(len(leg_handles)) if leg_handles[n] is not None]
            leg_handles = [leg_handles[n] for n in range(len(leg_handles)) if leg_handles[n] is not None]
            ax3d.legend(leg_handles, leg_labels, loc='upper left', bbox_to_anchor=(1.05, 1.0))

        def do_txt_ax():
            txt_ax.text(x=0.0, y=0.5, s=self.get_xrotor_output_text(), ha='left', va='center', fontfamily='consolas')
            txt_ax.axis('off')

        def do_radial_axes():
            xdata = self.xrotor_op_dict['r/R']
            for ylbl, ax in radial_axes.items():
                if ylbl in self.blade_data:
                    ax.plot(xdata, self.blade_data[ylbl], marker='*', markersize=4)
                else:
                    if ylbl in self.xrotor_op_dict:
                        ax.plot(xdata, self.xrotor_op_dict[ylbl], marker='o', markersize=3)

        def do_thrust_eff_ax():
            ax = radial_axes['thrust_eff']
            ax.set_ylabel('')
            ax.grid(False)
            thrust_eff = self.xrotor_op_dict['thrust(N)'] / self.xrotor_op_dict['power(W)']
            txt1 = 'Thrust Efficiency:\n\n\n\n\nNewtons / Watt'
            ax.text(x=0.5, y=0.5, s=txt1, ha='center', va='center')
            txt2 = '{:.3f}'.format(thrust_eff)
            ax.text(x=0.5, y=0.5, s=txt2, ha='center', va='center', fontsize=12, fontweight='bold')
            ax.axis('off')

            # disk loading metric
            ax.text(x=-0.3, y=0.5, s='Disk Loading:\n\n\n\n\nNewtons / Meter^2', ha='center', va='center')
            ax.text(x=-0.3, y=0.5, s='{:.3f}'.format(self.disk_loading), ha='center', va='center',
                    fontsize=12, fontweight='bold')

        do_ax3d()
        do_txt_ax()
        do_radial_axes()
        do_thrust_eff_ax()
        wsp = 0.60 if created_from_ui else 0.35
        fig.subplots_adjust(left=0.05, bottom=0.08, right=0.95, top=0.94, wspace=wsp, hspace=0.5)

        if savefig:
            savepath = os.path.join(os.getcwd(), '{}.png'.format(ax3d.get_title()))
            fig.savefig(savepath)
            Info('Saved PNG to "{}"'.format(savepath))

        return fig

    def plot_mpl3d_geometry(self, LE: bool = True, TE: bool = True, chords_betas: bool = True, hub: bool = True,
                            input_stations: bool = True, interp_profiles: bool = True, savefig: bool = False, fig=None):
        if fig is not None:
            ax3d = fig.axes[0]
            leg_anchor = (-0.15, 1.0)
        else:
            fig = plt.figure(figsize=[13, 10])
            ax3d = fig.add_subplot(111, projection='3d')
            leg_anchor = (0.90, 1.0)

        ax3d.set_xlabel('X')
        ax3d.set_ylabel('Y')
        ax3d.set_zlabel('Z')

        title_txt = 'Propeller Geometry - {}'.format(self.name)
        ax3d.set_title(title_txt)

        blades = np.arange(self.xrotor_d['Nblds'])
        angles = 360 / self.xrotor_d['Nblds'] * blades

        # plot le and te lines
        if LE:
            for ang in angles:
                le_pts, te_pts = self.get_blade_le_te(rotate_deg=ang)
                le_line, = ax3d.plot3D(xs=[pt[0] for pt in le_pts], ys=[pt[1] for pt in le_pts],
                                       zs=[pt[2] for pt in le_pts], c='k', lw=2)
        else:
            le_line = None

        if TE:
            for ang in angles:
                le_pts, te_pts = self.get_blade_le_te(rotate_deg=ang)
                te_line, = ax3d.plot3D(xs=[pt[0] for pt in te_pts], ys=[pt[1] for pt in te_pts],
                                       zs=[pt[2] for pt in te_pts], c='k', ls='-.', lw=2)
        else:
            te_line = None

        # plot stations
        if chords_betas:
            for ang in angles:
                chordlines = self.get_blade_chordlines(rotate_deg=ang)
                for line in chordlines:
                    xs, ys, zs = zip(*line)
                    station_line, = ax3d.plot3D(xs=xs, ys=ys, zs=zs, c='rosybrown', lw=1, ls='--')
        else:
            station_line = None

        # plot station_params
        if input_stations:
            radii = self.xrotor_d['r/R'] * self.radius
            chords = self.xrotor_d['C/R'] * self.radius
            betas = self.xrotor_d['Beta0deg'].copy()
            for roR, foil_name in self.station_params.items():
                # station dimensionalized parameters
                r = roR * self.radius
                ch = np.interp(r, radii, chords)
                beta = np.interp(r, radii, betas)
                sk = self.geo_params['tot_skew'] * roR

                # load the foil, shift, flip, and dimensionalize coordinates
                foil = Airfoil(foil_name, verbose=False)
                xc, yc, zc = funcs.generate_3D_profile_points(nondim_xy_coords=foil.get_coords(), radius=r,
                                                              axis_shift=0.25, chord_len=ch, beta_deg=beta,
                                                              skew_deg=sk)
                foils_line, = ax3d.plot3D(xs=xc, ys=yc, zs=zc, c='red', alpha=0.7, lw=1)
        else:
            foils_line = None

        # plot interpolated profiles
        if interp_profiles:
            for prof_num, prof_xyz in self.blade_xyz_profiles.items():
                xc, yc, zc = prof_xyz
                prof_line, = ax3d.plot3D(xs=xc, ys=yc, zs=zc, c='maroon', lw=1, alpha=0.7)
        else:
            prof_line = None

        # plot hub
        if hub:
            hub_thickness = abs(max([pt[2] for pt in le_pts]) - min([pt[2] for pt in te_pts]))
            theta = np.linspace(0, np.pi * 2, 50)
            hub_x = np.cos(theta) * self.hub_radius
            hub_y = np.sin(theta) * self.hub_radius
            top_zs = np.ones(len(hub_x)) * hub_thickness / 2
            bot_zs = -np.ones(len(hub_x)) * hub_thickness / 2
            hub_line, = ax3d.plot3D(xs=hub_x, ys=hub_y, zs=top_zs, c='gray', lw=2)
            hub_line, = ax3d.plot3D(xs=hub_x, ys=hub_y, zs=bot_zs, c='gray', lw=2)
        else:
            hub_line = None

        # set square axes and finish up formatting stuff
        lim = (-self.radius * 0.65, self.radius * 0.65)
        ax3d.set_xlim(lim)
        ax3d.set_ylim(lim)
        ax3d.set_zlim(lim)
        leg_handles = [le_line, te_line, hub_line, foils_line, station_line, prof_line]
        leg_labels = ['L.E.', 'T.E.', 'Hub', 'Input Stations', 'XROTOR Stations', 'Interpolated Geom.']

        leg_labels = [leg_labels[n] for n in range(len(leg_handles)) if leg_handles[n] is not None]
        leg_handles = [leg_handles[n] for n in range(len(leg_handles)) if leg_handles[n] is not None]
        ax3d.legend(leg_handles, leg_labels, loc='upper left', bbox_to_anchor=leg_anchor)

        return fig

    def plot_gl3d_geometry(self, LE: bool = True, TE: bool = True, chords_betas: bool = True, hub: bool = True,
                            input_stations: bool = True, interp_profiles: bool = True, view=None):
        if view is None:
            pg.mkQApp()
            self.gl_geo_view = view = gl.GLViewWidget()
            view.setFixedSize(1280, 720)
            view.show()
        else:
            pass

        blades = np.arange(self.xrotor_d['Nblds'])
        angles = 360 / self.xrotor_d['Nblds'] * blades

        # plot le and te lines
        if LE:
            for ang in angles:
                le_pts, te_pts = self.get_blade_le_te(rotate_deg=ang)
                le_line = gl.GLLinePlotItem(pos=le_pts, color=[0.5, 0.5, 0.5, 1.0], width=2, antialias=False,
                                            mode='line_strip', glOptions='opaque')
                view.addItem(le_line)

        if TE:
            for ang in angles:
                le_pts, te_pts = self.get_blade_le_te(rotate_deg=ang)
                te_line = gl.GLLinePlotItem(pos=te_pts, color=[0.5, 0.5, 0.5, 1.0], width=2, antialias=False,
                                            mode='line_strip', glOptions='opaque')
                view.addItem(te_line)

        # plot stations
        if chords_betas:
            for ang in angles:
                chordlines = self.get_blade_chordlines(rotate_deg=ang)
                for line in chordlines:
                    station_line = gl.GLLinePlotItem(pos=line, color=[i / 255 for i in [245, 66, 66, 255]],
                                                     width=2, antialias=False, mode='line_strip', glOptions='opaque')
                    view.addItem(station_line)

        # plot station_params
        if input_stations:
            radii = self.xrotor_d['r/R'] * self.radius
            chords = self.xrotor_d['C/R'] * self.radius
            betas = self.xrotor_d['Beta0deg'].copy()
            for roR, foil_name in self.station_params.items():
                # station dimensionalized parameters
                r = roR * self.radius
                ch = np.interp(r, radii, chords)
                beta = np.interp(r, radii, betas)
                sk = self.geo_params['tot_skew'] * roR

                # load the foil, shift, flip, and dimensionalize coordinates
                foil = Airfoil(foil_name, verbose=False)
                xc, yc, zc = funcs.generate_3D_profile_points(nondim_xy_coords=foil.get_coords(), radius=r,
                                                              axis_shift=0.25, chord_len=ch, beta_deg=beta,
                                                              skew_deg=sk)
                coords = list(zip(xc, yc, zc))
                foils_line = gl.GLLinePlotItem(pos=coords, color=[i / 255 for i in [5, 0, 163, 255]], width=2, antialias=False,
                                               mode='line_strip', glOptions='opaque')
                view.addItem(foils_line)

        # plot interpolated profiles
        if interp_profiles:
            for prof_num, prof_xyz in self.blade_xyz_profiles.items():
                xc, yc, zc = prof_xyz
                coords = list(zip(xc, yc, zc))
                prof_line = gl.GLLinePlotItem(pos=coords, color=[i / 255 for i in [163, 0, 0, 200]], width=2,
                                              antialias=False, mode='line_strip', glOptions='opaque')
                view.addItem(prof_line)

        # plot hub
        if hub:
            hub_thickness = abs(max([pt[2] for pt in le_pts]) - min([pt[2] for pt in te_pts]))
            theta = np.linspace(0, np.pi * 2, 50)
            hub_x = np.cos(theta) * self.hub_radius
            hub_y = np.sin(theta) * self.hub_radius
            top_zs = np.ones(len(hub_x)) * hub_thickness / 2
            bot_zs = -np.ones(len(hub_x)) * hub_thickness / 2
            hub_line = gl.GLLinePlotItem(pos=list(zip(hub_x, hub_y, top_zs)), color=[0.5, 0.5, 0.5, 1.0], width=2,
                                         antialias=False, mode='line_strip', glOptions='opaque')
            view.addItem(hub_line)
            hub_line_bot = gl.GLLinePlotItem(pos=list(zip(hub_x, hub_y, bot_zs)), color=[0.5, 0.5, 0.5, 1.0], width=2,
                                                          antialias=False, mode='line_strip', glOptions='opaque')
            view.addItem(hub_line_bot)

        # finish up formatting stuff
        lim = self.radius * 2.5
        view.setCameraPosition(distance=lim, azimuth=-90)
        zgrid = gl.GLGridItem()
        zgrid.setSize(2, 2, 2)
        zgrid.setSpacing(.2, .2, .2)
        zgrid.translate(0, 0, -0.5)
        view.addItem(zgrid)

        return view

    def plot_gl3d_wvel_data(self, total: bool = True, axial: bool = False, tangential: bool = False, view=None,
                            plot_every: int = 3):
        if view is None:
            pg.mkQApp()
            self.gl_wvel_view = view = gl.GLViewWidget()
            view.setFixedSize(1280, 720)
            view.show()
        else:
            pass

        blades = np.arange(self.xrotor_d['Nblds'])
        angles = 360 / self.xrotor_d['Nblds'] * blades

        self.gl3d_wvel_view = view = self.plot_gl3d_geometry(view=view)

        # plot vel vectors
        q_chord_pts = self.get_blade_quarter_chords()
        assert len(self.blade_data['r/R']) == len(q_chord_pts)
        for i, pt in enumerate(q_chord_pts):
            if i % plot_every == 0:
                va = self.blade_data['VA'][i]
                vt = self.blade_data['VT'][i]
                vd = self.blade_data['VD'][i]
                if total:
                    vector_root = pt
                    vector_tip = pt[0] - vd, pt[1] + vt, pt[2] - va
                    vector = Custom3DArrow(view=view, tip_root=[vector_tip, vector_root], width=3)
                if axial:
                    vector_root = pt
                    vector_tip = pt[0], pt[1], pt[2] - va
                    vector = Custom3DArrow(view=view, tip_root=[vector_tip, vector_root], width=3, color=(.05, .65, .13, 1))
                if tangential:
                    vector_root = pt
                    vector_tip = pt[0], pt[1] + vt, pt[2]
                    vector = Custom3DArrow(view=view, tip_root=[vector_tip, vector_root], width=3, color=(.92, .84, .2, 1))

        return view

    def generate_stl_geometry(self, plot_after: bool = True, verbose: bool = True):
        n_prof = len(self.blade_xyz_profiles)
        n_pts = np.max(np.shape(self.blade_xyz_profiles[0]))
        n_main_surf = (n_prof - 1) * 2 * (n_pts - 1)
        n_root = n_pts - 3
        n_tip = n_pts - 3
        n_tri = n_main_surf + n_root + n_tip

        mdata = np.zeros(n_tri, dtype=mesh.Mesh.dtype)

        tri_idx = 0

        # root profile
        vectors = funcs.compute_profile_trimesh(profile_coords=self.blade_xyz_profiles[0])  # outwards
        # vectors = funcs.compute_profile_trimesh(profile_coords=self.blade_xyz_profiles[0], reverse_order=True)  # inwards
        for vec in vectors:
            mdata['vectors'][tri_idx] = np.array(vec)
            tri_idx += 1

        # tip profile
        vectors = funcs.compute_profile_trimesh(profile_coords=self.blade_xyz_profiles[n_prof - 1], reverse_order=True)    # outwards
        # vectors = funcs.compute_profile_trimesh(profile_coords=self.blade_xyz_profiles[n_prof - 1])    # inwards
        for vec in vectors:
            mdata['vectors'][tri_idx] = np.array(vec)
            tri_idx += 1

        # iterate over the profiles
        for k in range(n_prof - 1):
            xyz_prof = self.blade_xyz_profiles[k]
            nxt_prof = self.blade_xyz_profiles[k + 1]

            # inter-profile surfaces
            for i in range(n_pts - 1):  # right hand rule to get normal direction correct
                a = xyz_prof[:, i]  # a is a point-coordinate in (x, y, z) format
                b = nxt_prof[:, i]  # same for b-f
                c = nxt_prof[:, i + 1]
                d = a.copy()
                e = c.copy()
                f = xyz_prof[:, i + 1]

                # outwards
                mdata['vectors'][tri_idx] = np.array([a, b, c])      # populate the array of triangle vectors
                mdata['vectors'][tri_idx + 1] = np.array([d, e, f])  # going in order, 2 triangles per iteration

                # inwards
                # mdata['vectors'][tri_idx] = np.array([c, b, a])      # populate the array of triangle vectors
                # mdata['vectors'][tri_idx + 1] = np.array([f, e, d])  # going in order, 2 triangles per iteration

                tri_idx += 2

        m = mesh.Mesh(mdata)

        if os.path.exists(self.stl_fpath):
            os.remove(self.stl_fpath)
        m.save(filename=self.stl_fpath)

        self.stl_mesh = mesh.Mesh.from_file(self.stl_fpath)
        if verbose:
            Info('Saved STL file and reloaded into propeller object: "{}"'.format(self.stl_fpath))

        if plot_after:
            self.plot_stl_mesh()

    def load_stl_geometry(self, verbose: bool = True):
        if os.path.exists(self.stl_fpath):
            self.stl_mesh = mesh.Mesh.from_file(self.stl_fpath)
            if verbose:
                Info('Loaded STL mesh data from file: {}'.format(self.stl_fpath))
        else:
            if verbose:
                Warning('STL file does not exist, use "generate_stl_geometry()" first')

    def plot_stl_mesh(self):
        if not hasattr(self, 'stl_view'):
            pg.mkQApp()
            self.stl_view = gl.GLViewWidget()
        view = self.stl_view
        view.clear()
        view.setFixedSize(1280, 720)
        view.show()

        grid = gl.GLGridItem()
        grid.scale(self.radius / 10, self.radius / 10, self.radius / 10)
        grid.translate(dx=0, dy=0, dz=-self.radius / 4)
        view.addItem(grid)
        view.setCameraPosition(distance=self.radius * 1.5, elevation=10, azimuth=-70)

        md = gl.MeshData(vertexes=self.stl_mesh.vectors.copy())
        mesh_itm = gl.GLMeshItem(meshdata=md, color=[0, 0, .7, 1], edgeColor=[.5, .5, .5, 1], drawEdges=False, drawFaces=True,
                                 shader='normalColor', smooth=False)
        mesh_itm.translate(dx=-0.5 * self.radius, dy=0, dz=0)
        view.addItem(mesh_itm)

        return view

    def plot_ideal_eff(self):
        Info('"{}" ideal efficiency: {:.1f}%'.format(self.name, self.ideal_eff))
        return

    def analyze_operating_point(self, velo: float = None, adva: float = None, rpm: float = None, thrust: float = None,
                                power: float = None, torque: float = None, xrotor_verbose: bool = False):

        funcs.run_xrotor_oper(xrr_file=self.xrr_file, vorform=self.design_vorform, adva=adva, rpm=rpm, thrust=thrust,
                              torque=torque, power=power, velo=velo, xrotor_verbose=xrotor_verbose)

    def analyze_sweep(self, velo_vals: list, sweep_param: str, sweep_vals: list, verbose: bool = True,
                      xrotor_verbose: bool = False, vorform: str = None, prog_signal=None):
        if sweep_param not in ['adva', 'rpm', 'thrust', 'power', 'torque']:
            raise Error('"sweep_param" must be one of ("adva", "rpm", "thrust", "power", "torque")')

        vorform = self.design_vorform if vorform is None else vorform

        total_pnts = len(velo_vals) * len(sweep_vals)
        if verbose:
            info_str = 'Analyzing "{}" across a sweep of {} operating points'.format(self.name, total_pnts)
            if prog_signal is not None:
                prog_signal.emit(0, [info_str])
            else:
                Info(info_str)
        count = 0
        for velo_val in velo_vals:
            for v, val in enumerate(sweep_vals):
                count += 1
                if verbose:
                    info_str = 'Analyzing sweep point # {} / {}'.format(count, total_pnts)
                    if prog_signal is not None:
                        prog_signal.emit(count / total_pnts * 100, [info_str])
                    else:
                        Info(info_str)
                try:
                    funcs.run_xrotor_oper(xrr_file=self.xrr_file, vorform=vorform, velo=velo_val, verbose=False,
                                          xrotor_verbose=xrotor_verbose, **{sweep_param: val})
                except Error as e:
                    warn_str = 'Failed to get XROTOR oper results for vel={}, {}={}\n{}'.format(velo_val, sweep_param, val, e)
                    if prog_signal is not None:
                        prog_signal.emit(None, [warn_str])
                    else:
                        Warning(warn_str)
                        pass

        self.oper_data.load_oper_sweep_results()
        self.wvel_data.load_wvel_sweep_results()
        if verbose:
            if prog_signal is not None:
                prog_signal.emit(0, 'Done!')
            else:
                Info('Done!')

    def clear_sweep_data(self):
        if os.path.exists(self.oper_data_dir):
            shutil.rmtree(self.oper_data_dir)
            Info('Removed {} and its contents'.format(self.oper_data_dir))
        if os.path.exists(self.wvel_data_dir):
            shutil.rmtree(self.wvel_data_dir)
            Info('Removed {} and its contents'.format(self.wvel_data_dir))


class PropellerOperData:
    def __init__(self, directory: str):
        self.directory = directory
        self.datapoints = {}
        self.prop_name = os.path.split(os.path.split(self.directory)[0])[1]

    def __len__(self):
        return len(self.datapoints)

    def get_swept_params(self):
        valid_params = VALID_OPER_PLOT_PARAMS
        swept_params = []
        avoid_params = []
        for param in valid_params:
            for dp in self.datapoints.values():
                if param not in swept_params:
                    pts = self.get_datapoints_by_paramval(param=param, val=dp[param])
                    if 2 < len(pts) < len(self.datapoints) and param not in avoid_params:
                        swept_params.append(param)
                    else:
                        avoid_params.append(param)

        return swept_params

    def get_oper_files(self, fullpath: bool = True):
        if os.path.exists(self.directory):
            if fullpath:
                return [os.path.join(self.directory, name) for name in os.listdir(self.directory) if name.endswith('.oper')]
            else:
                return [name for name in os.listdir(self.directory) if name.endswith('.oper')]
        else:
            return []

    def load_oper_sweep_results(self, verbose: bool = True):
        self.datapoints = d = {}
        fnames = self.get_oper_files(fullpath=False)
        for fname in fnames:
            vel_key, rpm_key = [float(num) for num in fname.strip('velo_').strip('.oper').split('_rpm_')]
            vel_key /= 100
            oper_fullpath = os.path.join(self.directory, fname)
            d[(vel_key, rpm_key)] = funcs.read_xrotor_op_file(fpath=oper_fullpath)
        if verbose and len(fnames) > 0:
            Info('Loaded Existing Oper Results (.oper)!', indent_level=1)

    def get_unique_param(self, param: str):
        uniq_vals = []
        for val in self.datapoints.values():
            if val[param] not in uniq_vals:
                uniq_vals.append(val[param])
        return list(sorted(uniq_vals))

    def get_datapoints_by_paramval(self, param: str, val: Union[float, int]):
        pnts = []
        for key, dp in self.datapoints.items():
            if dp[param] == val:
                pnts.append(dp)
        return pnts

    def plot(self, x_param: str, y_param: str, family_param: str = None, iso_param: str = None, fig=None, **plot_kwargs):
        params = [x_param, y_param, family_param, iso_param]
        valid_params = VALID_OPER_PLOT_PARAMS
        valid_params_lower = [s.lower() for s in valid_params]

        if len(self.datapoints) == 0:
            return

        for i, param in enumerate(params):
            if param is not None:
                if param.lower() in valid_params_lower:
                    params[i] = valid_params[valid_params_lower.index(param.lower())]
                if param.lower() in ['adv', 'adv.', 'adva', 'adv. ratio', 'adv.ratio']:
                    params[i] = 'adv. ratio'
                elif param.lower() in ['speed', 'speed(m/s)', 'vel', 'velocity', 'speed_mps']:
                    params[i] = 'speed(m/s)'
                elif param.lower() in ['thrust', 'thrust(n)', 'thrust (n)']:
                    params[i] = 'thrust(N)'
                elif param.lower() in ['power', 'power(w)', 'power (w)']:
                    params[i] = 'power(W)'
                elif param.lower() in ['torque(n-m)', 'torque', 'torque (n-m)']:
                    params[i] = 'torque(N-m)'
                elif param.lower() in ['eff', 'efficiency', 'Efficiency']:
                    params[i] = 'Efficiency'
                elif param.lower() in ['pvisc(w)', 'pvisc (w)', 'pvisc']:
                    params[i] = 'Pvisc(W)'
            else:
                params[i] = None

        x_param, y_param, family_param, iso_param = params

        if x_param not in valid_params:
            raise Error('x_param "{}" is not one of the valid params ({})'.format(x_param, valid_params))
        if y_param not in valid_params:
            raise Error('y_param "{}" is not one of the valid params ({})'.format(y_param, valid_params))
        if family_param not in valid_params and family_param is not None:
            raise Error('family_param error, must be one of {}'.format(valid_params))
        if iso_param not in valid_params and iso_param is not None:
            raise Error('iso_param error, must be one of {}'.format(valid_params))

        if fig is None:
            fig = plt.figure(figsize=[10, 8])
            ax = fig.add_subplot(111)
        else:
            ax = fig.axes[0]

        ax.grid(True)
        ax.set_title('{} Sweep Results'.format(self.prop_name))
        ax.set_xlabel(x_param)
        ax.set_ylabel(y_param)

        if family_param is not None:
            fvals = self.get_unique_param(param=family_param)
            for fval in fvals:
                datapts = self.get_datapoints_by_paramval(param=family_param, val=fval)
                xvals = [dp[x_param] for dp in datapts]
                yvals = [dp[y_param] for dp in datapts]
                xvals, yvals = zip(*sorted(zip(xvals, yvals)))
                ax.plot(xvals, yvals, '-o', label='{}'.format(fval))

            if iso_param is not None:
                ivals = self.get_unique_param(param=iso_param)
                for ival in ivals:
                    datapts = self.get_datapoints_by_paramval(param=iso_param, val=ival)
                    if len(datapts) > 1:
                        xvals = [dp[x_param] for dp in datapts]
                        yvals = [dp[y_param] for dp in datapts]
                        xvals, yvals = zip(*sorted(zip(xvals, yvals)))
                        ax.plot(xvals, yvals, '--', label='{}'.format(ival))

            leg_title = '{} /\n{}'.format(family_param, iso_param) if iso_param is not None else '{}'.format(family_param)
            ax.legend(title=leg_title, loc='best')
        else:
            datapts = self.datapoints.values()
            xvals = [dp[x_param] for dp in datapts]
            yvals = [dp[y_param] for dp in datapts]
            xvals, yvals = zip(*sorted(zip(xvals, yvals)))
            ax.plot(xvals, yvals, 'o')

        return fig


class PropellerWVelData:
    def __init__(self, directory: str):
        self.directory = directory
        self.datapoints = {}
        self.prop_name = os.path.split(os.path.split(self.directory)[0])[1]

    def __len__(self):
        return len(self.datapoints)

    def get_wvel_files(self, fullpath: bool = True):
        if os.path.exists(self.directory):
            if fullpath:
                return [os.path.join(self.directory, name) for name in os.listdir(self.directory) if name.endswith('.wvel')]
            else:
                return [name for name in os.listdir(self.directory) if name.endswith('.wvel')]
        else:
            return []

    def load_wvel_sweep_results(self, verbose: bool = True):
        self.datapoints = d = {}
        fnames = self.get_wvel_files(fullpath=False)
        for fname in fnames:
            vel_key, rpm_key = [float(num) for num in fname.strip('velo_').strip('.wvel').split('_rpm_')]
            vel_key /= 100
            wvel_fullpath = os.path.join(self.directory, fname)
            d[(vel_key, rpm_key)] = funcs.read_xrotor_wvel_file(fpath=wvel_fullpath)
        if verbose and len(fnames) > 0:
            Info('Loaded Existing WVel Results (.wvel)!', indent_level=1)
