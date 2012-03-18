#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys
import gconf

import logging
logger = logging.getLogger(__file__)

import gtk
import appindicator

import gettext
_ = gettext.gettext

from revelation import config, data, datahandler, dialog, entry, io, ui, util


class Config(config.Config):

    def __init__(self, basedir):
        super(Config, self).__init__(basedir)

    def get(self, key):
        value = self.client.get(self.__resolve_keypath(key))

        if value is None:

            schema_value = self.client.get(
                self.__resolve_keypath('/schemas%s' % key)
            )

            if schema_value is None:
                logger.debug('could not retrieve schema_value: %s', key)
                return None

            if schema_value.type == gconf.VALUE_SCHEMA:
                value = schema_value.get_schema().get_default_value()
                self.client.set_value(key, value)
            else:
                raise config.ConfigError

        if value.type == gconf.VALUE_STRING:
            return str(value.get_string())

        elif value.type == gconf.VALUE_INT:
            return value.get_int()

        elif value.type == gconf.VALUE_BOOL:
            return value.get_bool()


class RevelationIndicator(object):

    def __init__(self, filename=''):

        self.filename = filename

        if os.path.exists(self.filename):
            logger.debug('using provided file: %s', self.filename)

        self.ind = appindicator.Indicator(
            "revelation-indicator",
            "revelation-indicator-locked", #defines icon
            appindicator.CATEGORY_APPLICATION_STATUS
        )

        self.ind.set_status(appindicator.STATUS_ACTIVE)

        sys.excepthook	= self.__cb_exception

        gettext.bindtextdomain(config.PACKAGE, config.DIR_LOCALE)
        gettext.bind_textdomain_codeset(config.PACKAGE, "UTF-8")
        gettext.textdomain(config.PACKAGE)

        try:
            self.__init_config(filename)
            self.__init_facilities()
            self.__init_ui()

        except config.ConfigError:
            dialog.Error(
                None,
                _('Missing configuration data'),
                _('The applet could not find its configuration data, please'
                  'reinstall Revelation.')
            ).run()
            sys.exit(1)

    def __init_config(self, filename=''):
        self.config = Config("/apps/revelation-indicator/prefs")

        ##FIXME: use a better way to set the filename


    def __init_facilities(self):
        "Sets up facilities"

        self.clipboard = data.Clipboard()
        self.datafile = io.DataFile(datahandler.Revelation)
        self.entrystore = data.EntryStore()
        #self.items = ui.ItemFactory(self.applet)
        self.locktimer = data.Timer()

        self.config.monitor(
            "autolock_timeout",
            lambda k,v,d: self.locktimer.start(v * 60)
        )
        self.config.monitor("file", self.__cb_config_file)

        self.datafile.connect("changed", self.__cb_file_changed)
        self.datafile.connect("content-changed", self.__cb_file_content_changed)
        self.locktimer.connect("ring", self.__cb_file_autolock)


    def __init_ui(self):
        self.menu = gtk.Menu()

        self.database_item = gtk.MenuItem(_('Database'))
        self.database_item.show()
        self.database_item.set_sensitive(False)

        self.unlock_item = gtk.MenuItem(_('Unlock File'))
        self.unlock_item.show()
        self.unlock_item.connect(
            'activate',
            lambda w,d=None: self.file_open(self.config.get("file"))
        )

        self.lock_item = gtk.MenuItem(_('Lock File'))
        self.lock_item.connect(
            'activate',
            lambda w,d=None: self.file_close()
        )

        self.prefs_item = gtk.MenuItem(_('Preferences'))
        self.prefs_item.show()
        self.prefs_item.connect(
            'activate',
            lambda w,d=None: self.prefs()
        )

        self.about_item = gtk.MenuItem(_('About'))
        self.about_item.show()
        self.about_item.connect('activate', self.__cb_about)

        self.quit_item = gtk.MenuItem('Quit')
        self.quit_item.show()
        self.quit_item.connect('activate', gtk.main_quit)

        self.menu.append(self.database_item)
        self.menu.append(gtk.SeparatorMenuItem())
        self.menu.append(self.unlock_item)
        self.menu.append(self.lock_item)
        self.menu.append(gtk.SeparatorMenuItem())
        self.menu.append(self.prefs_item)
        self.menu.append(self.about_item)
        self.menu.append(self.quit_item)

        self.ind.set_menu(self.menu)
        #self.menu.show_all()

        gtk.about_dialog_set_url_hook(
            lambda d,l: gtk.show_uri(None, l, gtk.get_current_event_time())
        )

	gtk.about_dialog_set_email_hook(
            lambda d,l: gtk.show_uri(None, "mailto:" + l, gtk.get_current_event_time())
        )

        ## set up various ui element holders
        self.popup_entryview	= None
        self.popup_entrylist	= None


    def file_close(self):
        logger.debug(_("closing unlocked database file."))
        ##FIXME: check how this works and if it is necessary
        self.__close_popups()
        self.locktimer.stop()

        ##FIXME: calling a revelation method?
        self.datafile.close()
        self.entrystore.clear()

        ##TODO: reset the menu entry
        ##FIXME: is it required to remove subsubmenus first??
        self.database_item.remove_submenu()
        self.database_item.set_sensitive(False)

        self.ind.set_icon("revelation-indicator-locked")
        self.unlock_item.show()
        self.lock_item.hide()

    def file_open(self, file, password = None):
        logger.debug(_("opening database file."))
        try:

            success = self.__file_load(file, password)

            self.ind.set_icon("revelation-indicator-unlocked")
            self.lock_item.show()
            self.unlock_item.hide()

            return success

        except dialog.CancelError:
            pass

        except datahandler.FormatError:
            dialog.Error(None, _('Invalid file format'), _('The file \'%s\' contains invalid data.') % file).run()

        except ( datahandler.DataError, entry.EntryTypeError, entry.EntryFieldError ):
            dialog.Error(
                None,
                _('Unknown data'),
                _(
                    'The file \'%s\' contains unknown data. It may have been '
                    'created by a more recent version of Revelation.'
                ) % file
            ).run()

        except datahandler.PasswordError:
            dialog.Error(
                None,
                _('Incorrect password'),
                _(
                    'You entered an incorrect password for the file '
                    '\'%s\', please try again.'
                ) % file
            ).run()
            self.file_open(file, None)

        except datahandler.VersionError:
            dialog.Error(
                None,
                _('Unknown data version'),
                _('The file \'%s\' has a future version number, please upgrade Revelation to open it.') % file
            ).run()

        except IOError:
            dialog.Error(
                None,
                _('Unable to open file'),
                _('The file \'%s\' could not be opened. Make sure that the file exists, and that you have permissions to open it.') % file
            ).run()

        return False


    def prefs(self):
        dialog.run_unique(Preferences, None, self.config)


    def __cb_config_file(self, key, value, data):
            "Config callback for file key changes"

            ###FIXME: is this really necessary???
            ##self.file_close()
            ##TODO: fix this
            #self.applet.get_popup_component().set_prop("/commands/file-unlock", "sensitive", self.config.get("file") != "" and "1" or "0")

            pass


    def __cb_file_autolock(self, widget, data = None):
        "Callback for autolocking the file"

        if self.config.get("autolock") == True:
            self.file_close()


    def __cb_file_content_changed(self, widget, data = None):
        "Callback for changed file content"

        try:
            self.__file_load(self.datafile.get_file(), self.datafile.get_password())

        except dialog.CancelError:
            pass

        except datahandler.PasswordError:
            self.file_close()

        except datahandler.Error:
            pass


    def __cb_file_changed(self, widget, data = None):
        "Callback for changed data file"
        logger.debug('file has been changed')

        ##FIXME:
        #popup = self.applet.get_popup_component()

        #if self.datafile.get_file() == None:
        #        self.entry.set_text("")

        #        popup.set_prop("/commands/file-unlock", "sensitive", self.config.get("file") != "" and "1" or "0")
        #        popup.set_prop("/commands/file-lock", "sensitive", "0")

        #        self.icon.set_from_stock(ui.STOCK_REVELATION_LOCKED, ui.ICON_SIZE_APPLET)

        #else:
        #        popup.set_prop("/commands/file-unlock", "sensitive", "0")
        #        popup.set_prop("/commands/file-lock", "sensitive", "1")

        #        self.icon.set_from_stock(ui.STOCK_REVELATION, ui.ICON_SIZE_APPLET)


    def __cb_popup_activate(self, widget, data = None):
        self.locktimer.reset()

        #action = self.config.get("menuaction")

        #if action == "show":
        self.entry_show(data)

        #elif action == "copy":
        #    self.entry_copychain(data)

        #elif self.__launcher_valid(data):
        #    self.entry_goto(data)

        #else:
        #    self.entry_show(data)


    def entry_show(self, e, focusafter = False):
        self.__close_popups()

        self.popup_entryview = EntryViewPopup(e, self.config, self.clipboard)

        if focusafter == True:
            self.popup_entryview.connect("closed", lambda w: self.__focus_entry())

        def cb_goto(widget):
            if self.__launcher_valid(e):
                self.entry_goto(e)

            self.popup_entryview.close()

        #self.popup_entryview.button_goto.connect("clicked", cb_goto)
        #self.popup_entryview.button_goto.set_sensitive(self.__launcher_valid(e))

        self.popup_entryview.realize()
        x, y = self.__get_popup_offset(self.popup_entryview)
        self.popup_entryview.show(x, y)

    def __close_popups(self):
        "Closes any open popups"

        self.locktimer.reset()

        if hasattr(self, "popup_entryview") == True and self.popup_entryview != None:
            self.popup_entryview.destroy()

        if hasattr(self, "popup_entrylist") == True and self.popup_entrylist != None:
            self.popup_entrylist.destroy()


    def __file_load(self, filename, password = None):

        if not filename:
            logger.debug("no revelation database provided")
            return False

        if dialog.present_unique(dialog.PasswordOpen) == True:
            logger.debug('password dialog already opened')
            return False

        entrystore = self.datafile.load(
            filename,
            password,
            lambda: dialog.run_unique(
                dialog.PasswordOpen,
                None,
                os.path.basename(filename)
            )
        )

        self.entrystore.clear()
        self.entrystore.import_entry(entrystore, None)

        menu = self.__generate_entrymenu(self.entrystore)
        self.database_item.set_submenu(menu)
        self.database_item.set_sensitive(True)

        self.menu.show_all()

        self.locktimer.start(self.config.get("autolock_timeout") * 60)

        self.__close_popups()

        return True

    def __focus_entry(self):
        ##FIXME:
        ##self.applet.request_focus(long(0))
        pass

    def __generate_entrymenu(self, entrystore, parent = None):
        menu = gtk.Menu()

        for i in range(entrystore.iter_n_children(parent)):
            iter = entrystore.iter_nth_child(parent, i)

            e = entrystore.get_entry(iter)
            item = ui.ImageMenuItem(type(e) == entry.FolderEntry and ui.STOCK_FOLDER or e.icon, e.name)
            item.connect("select", lambda w,d=None: self.locktimer.reset())

            if type(e) == entry.FolderEntry:
                item.set_submenu(self.__generate_entrymenu(entrystore, iter))
            else:
                item.connect("activate", self.__cb_popup_activate, e)

            menu.append(item)

        return menu


    def __get_launcher(self, e):
        command = self.config.get("/apps/revelation/launcher/%s" % e.id)

        if command in ( "", None ):
            return None

        subst = {}
        for field in e.fields:
            subst[field.symbol] = field.value

        command = util.parse_subst(command, subst)

        return command

    def __get_popup_offset(self, popup):
        x = gtk.gdk.screen_width() / 2
        y = 50

        return x, y

    def __launcher_valid(self, e):
        try:
            command = self.__get_launcher(e)

            return command != None

        except ( util.SubstFormatError ):
            return True

        except ( util.SubstValueError, config.ConfigError ):
            return False

    def __require_file(self):
        if self.datafile.get_file() != None:
            return True

        if self.config.get("file") != "":
            return self.file_open(self.config.get("file"))

        d = dialog.Info(
            None, _('File not selected'),
            _('You must select a Revelation data file to use - this can be done in the applet preferences.'),
            ( ( gtk.STOCK_PREFERENCES, gtk.RESPONSE_ACCEPT ), ( gtk.STOCK_OK, gtk.RESPONSE_OK ) )
        )


        if d.run() == gtk.RESPONSE_ACCEPT:
            self.prefs()

        return False

    def __cb_about(self, item):
        dialog = gtk.AboutDialog()
        dialog.set_name(_('Revelation Indicator'))
        dialog.set_comments(_('An indicator applet to browse a Revelation database'))
        dialog.set_version("0.1")
        dialog.set_copyright("(c) Sebastian Vetter")
        dialog.run()
        dialog.destroy()

    def __cb_exception(self, type, value, trace):

        if type == KeyboardInterrupt:
            sys.exit(1)

        traceback = util.trace_exception(type, value, trace)
        sys.stderr.write(traceback)

        if dialog.Exception(None, traceback).run() == True:
            gtk.main()
        else:
            sys.exit(1)


class Preferences(dialog.Utility):

    def __init__(self, parent, cfg):
        dialog.Utility.__init__(self, parent, "Preferences")
        self.config = cfg
        self.set_modal(False)

        self.notebook = ui.Notebook()
        self.vbox.pack_start(self.notebook)

        self.page_general = self.notebook.create_page(_('General'))
        self.__init_section_file(self.page_general)
        #self.__init_section_menuaction(self.page_general)
        #self.__init_section_misc(self.page_general)

        self.connect("response", lambda w,d: self.destroy())


    def __init_section_file(self, page):
        self.section_file = page.add_section(_('File Handling'))

        # entry for file
        self.button_file = ui.FileButton(_('Select File to Use'))
        ui.config_bind(self.config, "file", self.button_file)

        eventbox = ui.EventBox(self.button_file)
        eventbox.set_tooltip_text(_('The data file to search for accounts in'))
        self.section_file.append_widget(_('File to use'), eventbox)

        # check-button for autolock
        self.check_autolock = ui.CheckButton(_('Lock file when inactive for'))
        ui.config_bind(self.config, "autolock", self.check_autolock)
        self.check_autolock.connect("toggled", lambda w: self.spin_autolock_timeout.set_sensitive(w.get_active()))
        self.check_autolock.set_tooltip_text(_('Automatically lock the file after a period of inactivity'))

        # spin-entry for autolock-timeout
        self.spin_autolock_timeout = ui.SpinEntry()
        self.spin_autolock_timeout.set_range(1, 120)
        self.spin_autolock_timeout.set_sensitive(self.check_autolock.get_active())
        ui.config_bind(self.config, "autolock_timeout", self.spin_autolock_timeout)
        self.spin_autolock_timeout.set_tooltip_text(_('The period of inactivity before locking the file, in minutes'))

        # container for autolock-widgets
        hbox = ui.HBox()
        hbox.set_spacing(3)
        hbox.pack_start(self.check_autolock)
        hbox.pack_start(self.spin_autolock_timeout)
        hbox.pack_start(ui.Label(_('minutes')))
        self.section_file.append_widget(None, hbox)

    #def __init_section_menuaction(self, page):
    #    "Sets up a menuaction section in a page"

    #    self.section_menuaction = page.add_section(_('Menu Action'))

    #    # radio-button for show
    #    self.radio_show = ui.RadioButton(None, _('Display account info'))
    #    ui.config_bind(self.config, "menuaction", self.radio_show, "show")

    #    self.radio_show.set_tooltip_text(_('Display the account information'))
    #    self.section_menuaction.append_widget(None, self.radio_show)

    #    # radio-button for goto
    #    self.radio_goto = ui.RadioButton(self.radio_show, _('Go to account, if possible'))
    #    ui.config_bind(self.config, "menuaction", self.radio_goto, "goto")

    #    self.radio_goto.set_tooltip_text(_('Open the account in an external application if possible, otherwise display it'))
    #    self.section_menuaction.append_widget(None, self.radio_goto)

    #    # radio-button for copy username/password
    #    self.radio_copy = ui.RadioButton(self.radio_show, _('Copy password to clipboard'))
    #    ui.config_bind(self.config, "menuaction", self.radio_copy, "copy")

    #    self.radio_copy.set_tooltip_text(_('Copy the account password to the clipboard'))
    #    self.section_menuaction.append_widget(None, self.radio_copy)

    #def __init_section_misc(self, page):
    #    "Sets up the misc section"

    #    self.section_misc = page.add_section(_('Miscellaneous'))

    #    # show searchentry checkbutton
    #    self.check_show_searchentry = ui.CheckButton(_('Show search entry'))
    #    ui.config_bind(self.config, "show_searchentry", self.check_show_searchentry)

    #    self.check_show_searchentry.set_tooltip_text(_('Display an entry box in the applet for searching'))
    #    self.section_misc.append_widget(None, self.check_show_searchentry)

    #    # show passwords checkbutton
    #    self.check_show_passwords = ui.CheckButton(_('Show passwords and other secrets'))
    #    ui.config_bind(self.config, "show_passwords", self.check_show_passwords)

    #    self.check_show_passwords.set_tooltip_text(_('Display passwords and other secrets, such as PIN codes (otherwise, hide with ******)'))
    #    self.section_misc.append_widget(None, self.check_show_passwords)

    #    # check-button for username
    #    self.check_chain_username = ui.CheckButton(_('Also copy username when copying password'))
    #    ui.config_bind(self.config, "chain_username", self.check_chain_username)

    #    self.check_chain_username.set_tooltip_text(_('When the password is copied to clipboard, put the username before the password as a clipboard "chain"'))
    #    self.section_misc.append_widget(None, self.check_chain_username)


    def run(self):
            self.show_all()


class EntryViewPopup(dialog.Popup):

    def __init__(self, e, cfg=None, clipboard=None):
        dialog.Popup.__init__(self)
        self.set_title(e.name)

        self.entryview = ui.EntryView(cfg, clipboard)
        self.entryview.set_border_width(0)
        self.entryview.display_entry(e)

        self.button_close = ui.Button(gtk.STOCK_CLOSE, lambda w: self.close())
        self.buttonbox = ui.HButtonBox(self.button_close)

        self.vbox = ui.VBox(self.entryview, self.buttonbox)
        self.vbox.set_border_width(12)
        self.vbox.set_spacing(15)

        self.add(self.vbox)

        self.connect("show", lambda w: self.button_close.grab_focus())
