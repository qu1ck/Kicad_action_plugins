# -*- coding: utf-8 -*-
#  action_length_stats.py
#
# Copyright (C) 2018 Mitja Nemec
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

import wx
import pcbnew
import os
import logging
import sys
import timeit

import lenght_stats_GUI

SCALE = 1000000.0

class LenghtStatsDialog(lenght_stats_GUI.LenghtStatsGUI):
    # hack for new wxFormBuilder generating code incompatible with old wxPython
    # noinspection PyMethodOverriding
    def SetSizeHints(self, sz1, sz2):
        try:
            # wxPython 3
            self.SetSizeHintsSz(sz1, sz2)
        except TypeError:
            # wxPython 4
            super(SettingsDialog, self).SetSizeHints(sz1, sz2)

    def __init__(self,  parent, board, netname):
        lenght_stats_GUI.LenghtStatsGUI.__init__(self, parent)

        self.net_list.InsertColumn(0, 'Net', width=100) 
        self.net_list.InsertColumn(1, 'Length')

        for net in netname:
            index_net = netname.index(net)
            index = self.net_list.InsertStringItem(index_net, net)
            self.net_list.SetStringItem(index, 1, "0.0")

        self.board = board
        self.netname = netname

        self.timer = wx.Timer(self, 1)
        self.refresh_time = 0.1

        self.Bind(wx.EVT_TIMER, self.on_update, self.timer)

    def cont_refresh_toggle(self, event):
        if self.chk_cont.IsChecked():
            self.timer.Start(self.refresh_time * 10 * 1000)
        else:
            self.timer.Stop()
        event.Skip()

    def on_btn_refresh(self, event):
        self.refresh()
        event.Skip()

    def on_btn_ok(self, event):
        event.Skip()

    def on_update(self, event):
        self.refresh()
        event.Skip()

    def refresh(self):
        start_time = timeit.default_timer()
        # get all tracks
        tracks = self.board.GetTracks()

        # find only tracks on this net
        for net in self.netname:
            tracks_on_net = []
            for t in tracks:
                if t.GetNetname() == net:
                    tracks_on_net.append(t)

            # sum their lenght
            length = 0
            for t in tracks_on_net:
                length = length + t.GetLength()/SCALE

            index_net = self.netname.index(net)
            self.net_list.SetStringItem(index_net, 1, "%.2f" % length)

        stop_time = timeit.default_timer()
        delta_time = stop_time - start_time
        if delta_time > 0.05:
            self.refresh_time = delta_time
        else:
            self.refresh_time = 0.05
        self.lbl_refresh_time.SetLabelText(u"Refresh time: %.2f s" % delta_time)

class LengthStats(pcbnew.ActionPlugin):
    """
    A plugin to show track lenght of all selected nets
    How to use:
    - move to GAL
    - select track segment or pad for net you wish to find the length
    - call the plugin
    """

    def defaults(self):
        self.name = "Length stats"
        self.category = "Get tracks lenght"
        self.description = "Obtains and refreshes lenght of all tracks on selected nets"

    def Run(self):
        # load board
        board = pcbnew.GetBoard()

        # go to the project folder - so that log will be in proper place
        os.chdir(os.path.dirname(os.path.abspath(board.GetFileName())))

        # set up logger
        logging.basicConfig(level=logging.DEBUG,
                            filename="length_stats.log",
                            filemode='w',
                            format='%(asctime)s %(name)s %(lineno)d:%(message)s',
                            datefmt='%m-%d %H:%M:%S',
                            disable_existing_loggers=False)
        logger = logging.getLogger(__name__)
        logger.info("Action plugin Length stats started")

        stdout_logger = logging.getLogger('STDOUT')
        sl_out = StreamToLogger(stdout_logger, logging.INFO)
        sys.stdout = sl_out

        stderr_logger = logging.getLogger('STDERR')
        sl_err = StreamToLogger(stderr_logger, logging.ERROR)
        sys.stderr = sl_err

        _pcbnew_frame = \
            filter(lambda w: w.GetTitle().lower().startswith('pcbnew'),
                   wx.GetTopLevelWindows()
                  )[0]

        # find all selected tracks and pads
        nets = set()
        selected_tracks = filter(lambda x: x.IsSelected(), board.GetTracks())

        nets.update([track.GetNetname() for track in selected_tracks])

        modules = board.GetModules()
        for mod in modules:
            pads = mod.Pads()
            nets.update([pad.GetNetname() for pad in pads if pad.IsSelected()])

        dlg = LenghtStatsDialog(_pcbnew_frame, board, list(nets))

        dlg.Show()


class StreamToLogger(object):
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """
    def __init__(self, logger, log_level=logging.INFO):
        self.logger = logger
        self.log_level = log_level
        self.linebuf = ''

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())