from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph.opengl as gl
from pyqtgraph.opengl.GLGraphicsItem import GLGraphicsItem
import OpenGL.GL as ogl
import numpy as np


class Custom3DAxis(gl.GLAxisItem):
    """Class defined to extend 'gl.GLAxisItem'."""
    def __init__(self, parent, color=(0,0,0,.6)):
        # gl.GLAxisItem.__init__(self)
        super(Custom3DAxis, self).__init__()
        self.parent = parent
        self.c = color

    def add_labels(self, xlbl: str = None, ylbl: str = None, zlbl: str = None):
        """Adds axes labels."""
        x,y,z = self.size()
        #X label
        if xlbl is not None:
            self.xLabel = gl.GLTextItem(pos=(x/2, -y/3, -z/20), text=xlbl)
            self.parent.addItem(self.xLabel)
        #Y label
        if ylbl is not None:
            self.yLabel = gl.GLTextItem(pos=(-x/3, y/2, -z/20), text=ylbl)
            self.parent.addItem(self.yLabel)
        #Z label
        if zlbl is not None:
            self.zLabel = gl.GLTextItem(pos=(-x/3, -y/3, z/2), text=zlbl)
            self.parent.addItem(self.zLabel)

    def add_tick_values(self, xticks=[], yticks=[], zticks=[]):
        """Adds ticks values."""
        x,y,z = self.size()
        xtpos = np.linspace(0, x, len(xticks))
        ytpos = np.linspace(0, y, len(yticks))
        ztpos = np.linspace(0, z, len(zticks))
        #X label
        for i, xt in enumerate(xticks):
            val = gl.GLTextItem(pos=(xtpos[i], -y/20, -z/20), text='{:.1f}'.format(xt))
            self.parent.addItem(val)
        #Y label
        for i, yt in enumerate(yticks):
            val = gl.GLTextItem(pos=(-x/20, ytpos[i], -z/20), text='{:.1f}'.format(yt))
            self.parent.addItem(val)
        #Z label
        for i, zt in enumerate(zticks):
            val = gl.GLTextItem(pos=(-x/20, -y/20, ztpos[i]), text='{:.1f}'.format(zt))
            self.parent.addItem(val)

    def paint(self):
        self.setupGLState()
        if self.antialias:
            ogl.glEnable(ogl.GL_LINE_SMOOTH)
            ogl.glHint(ogl.GL_LINE_SMOOTH_HINT, ogl.GL_NICEST)
        ogl.glBegin(ogl.GL_LINES)

        x,y,z = self.size()
        #Draw Z
        ogl.glColor4f(self.c[0], self.c[1], self.c[2], self.c[3])
        ogl.glVertex3f(0, 0, 0)
        ogl.glVertex3f(0, 0, z)
        #Draw Y
        ogl.glColor4f(self.c[0], self.c[1], self.c[2], self.c[3])
        ogl.glVertex3f(0, 0, 0)
        ogl.glVertex3f(0, y, 0)
        #Draw X
        ogl.glColor4f(self.c[0], self.c[1], self.c[2], self.c[3])
        ogl.glVertex3f(0, 0, 0)
        ogl.glVertex3f(x, 0, 0)
        ogl.glEnd()


class Custom3DArrow(GLGraphicsItem):
    def __init__(self, view: gl.GLViewWidget, color: tuple = (0, 0, 1, 1), width: int = 2, length: float = None, tip_root: list = None):
        super(Custom3DArrow, self).__init__()
        self.view = view

        if length is None and tip_root is None:
            length = 1

        if length is None:
            assert len(tip_root) == 2
            xtip, ytip, ztip = tip_root[0]
            xroot, yroot, zroot = tip_root[1]
            length = np.sqrt((xtip - xroot) ** 2 + (ytip - yroot) ** 2 + (ztip - zroot) ** 2)
        else:
            xtip, ytip, ztip = 0, 0, 0
            xroot, yroot, zroot = 0, 0, -length
            tip_root = [[xtip, ytip, ztip], [xroot, yroot, zroot]]
        dx, dy, dz = [tip - root for tip, root in zip([xtip, ytip, ztip], [xroot, yroot, zroot])]
        shaft_root = [xroot, yroot, zroot]
        shaft_tip = [xroot + 0.75 * dx, yroot + 0.75 * dy, zroot + 0.75 * dz]

        self.shaft = gl.GLLinePlotItem(pos=[shaft_root, shaft_tip], color=color, width=width, antialias=False, mode='line_strip', glOptions='opaque')
        tip_length, tip_width = 0.25 * length, 0.08 * length
        tip = gl.MeshData.cylinder(rows=2, cols=15, radius=[tip_width, 0.001 * tip_width], length=tip_length,
                                   offset=False)
        self.tip_mesh = gl.GLMeshItem(meshdata=tip, smooth=True, color=color, shader='shaded', glOptions='opaque')
        self.view.addItem(self.shaft)
        self.view.addItem(self.tip_mesh)

        x_deg = np.rad2deg(np.arctan2(-dy, dz))
        y_deg = np.rad2deg(np.arctan2(dx, -dz))
        self.tip_mesh.translate(dx=0, dy=0, dz=-tip_length)
        self.tip_mesh.rotate(x_deg, 1, 0, 0)
        self.tip_mesh.rotate(y_deg, 0, 1, 0)
        self.tip_mesh.translate(dx=xtip, dy=ytip, dz=ztip)

    def translate(self, dx, dy, dz, local=False):
        self.shaft.translate(dx, dy, dz, local=local)
        self.tip_mesh.translate(dx, dy, dz, local=local)

    def rotate(self, angle, x, y, z, local=False):
        self.shaft.rotate(angle, x, y, z, local=local)
        self.tip_mesh.rotate(angle, x, y, z, local=local)
