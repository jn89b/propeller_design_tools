import sys
import os
from propeller_design_tools.user_io import Error, Input, Info
import pkg_resources


VALID_OPER_PLOT_PARAMS = ['adv. ratio', 'J', 'speed(m/s)', 'rpm', 'thrust(N)', 'power(W)', 'torque(N-m)', 'Efficiency',
                          'Eff induced', 'Eff ideal', 'Pvisc(W)', 'Ct', 'Tc', 'Cp', 'Pc', 'Sigma']


def set_airfoil_database(path: str):
    _save_settings({'airfoil_database': path})
    return


def set_propeller_database(path: str):
    _save_settings({'propeller_database': path})
    return


def get_prop_db():
    usr_db = _get_user_settings()['propeller_database']
    if os.path.isdir(usr_db):
        return usr_db
    else:
        def_db = _get_default_propeller_database()
        if os.path.isdir(def_db):
            return def_db
        else:
            raise Error('Cannot find either propeller database option (user-set = "{}", default = "{}")'.format(usr_db, def_db))


def get_foil_db():
    usr_db = _get_user_settings()['airfoil_database']
    if os.path.isdir(usr_db):
        return usr_db
    else:
        def_db = _get_default_airfoil_database()
        if os.path.isdir(def_db):
            return def_db
        else:
            raise Error('Cannot find either airfoil database option (user-set = "{}", default = "{}")'.format(usr_db, def_db))


def get_setting(s: str):
    if s not in _get_user_settings():
        raise Error('"" is not a known PDT setting'.format(s))
    else:
        return _get_user_settings()[s]


def _get_cursor_fpath():
    fname = pkg_resources.resource_filename(__name__, 'supporting_files/crosshair_cursor.png')
    return fname


def _get_gunshot_1_fpath():
    fname = pkg_resources.resource_filename(__name__, 'supporting_files/gunshot1.wav')
    return fname


def _get_gunshot_2_fpath():
    fname = pkg_resources.resource_filename(__name__, 'supporting_files/gunshot2.wav')
    return fname


def _get_gunshot_3_fpath():
    fname = pkg_resources.resource_filename(__name__, 'supporting_files/gunshot3.wav')
    return fname


def _get_gunshot_4_fpath():
    fname = pkg_resources.resource_filename(__name__, 'supporting_files/gunshot4.wav')
    return fname


def _get_gunshot_fpaths():
    return [_get_gunshot_1_fpath(), _get_gunshot_2_fpath(), _get_gunshot_3_fpath(), _get_gunshot_4_fpath()]


def _get_settings_fpath():
    fname = pkg_resources.resource_filename(__name__, 'supporting_files/user-settings.txt')
    return fname


def _get_default_propeller_database():
    fname = pkg_resources.resource_filename(__name__, 'prop_database')
    return fname


def _get_default_airfoil_database():
    fname = pkg_resources.resource_filename(__name__, 'foil_database')
    return fname


def _save_settings(new_sett: dict = None):
    defaults = {
        'airfoil_database': _get_default_airfoil_database(),
        'propeller_database': _get_default_propeller_database(),
    }

    if new_sett is None:
        new_sett = {}

    savepath = _get_settings_fpath()

    if os.path.exists(savepath):
        old_sett = _get_user_settings(settings_path=savepath)
    else:
        old_sett = {}

    with open(savepath, 'w') as f:
        for key in defaults:
            if key in new_sett:
                val = new_sett[key]
            elif key in old_sett:
                val = old_sett[key]
            else:
                val = defaults[key]
            f.write('{}: {}\n'.format(key, val))

    return


def _get_user_settings(settings_path: str = None) -> dict:
    if settings_path is None:
        settings_path = _get_settings_fpath()

    with open(settings_path, 'r') as f:
        txt = f.read().strip()

    lines = [ln for ln in txt.split('\n') if ln.strip() != '']
    settings = {}
    for line in lines:
        key, val = line.split(': ', 1)
        if val == 'None':
            val = None
        elif val == 'True':
            val = True
        elif val == 'False':
            val = False
        settings[key] = val

    return settings
