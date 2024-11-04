import wx
import os
import json
from functools import partial, wraps
from abc import abstractmethod
import zipfile
import shutil


class JSONFile():
    def __init__(self, path) -> None:
        self.path = path

        if os.path.exists(path):
            with open(path, 'r') as f:
                self.content = json.load(f)
        else:
            self.content = self._init_file()
    
    @abstractmethod
    def _init_file(self):
        raise NotImplementedError('_init_file() must be implemented in the JSONFile subclass.')

    @classmethod
    def _update_file(cls, func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            result = func(self, *args, **kwargs)
            with open(self.path, 'w') as f:
                json.dump(self.content, f, indent=1)
            return result
        return wrapper


class ModFile():
    def __init__(self, path) -> None:
        self.path = path

    def read(self):
        with open(self.path, 'r') as f:
            lines = f.read().split('\n')

        content = {}
        for i,line in enumerate(lines):
            if line.startswith('}'):
                continue
            name = line.split('=')[0]
            value = line.split('=')[1].strip('"')
            if value != '{':
                content[name] = value
            else:
                content[name] = []
                while lines[i+1].startswith('\t'):
                    value = lines[i+1].split('\t')[1].strip('"')
                    content[name].append(value)
                    lines.pop(i+1)

        return content
                        
    def write(self, content:dict):
        text = ''
        for name,value in content.items():
            if isinstance(value, str):
                text += f'{name}="{value}"\n'
            else:
                list_text = ''
                for tag in value:
                    list_text += f'\t"{tag}"\n'
                text += name+'={\n'+list_text+'}\n'

        with open(self.path, 'w') as f:
            f.write(text)
    
    def get_path(self):
        return self.path


class UserSettings(JSONFile):
    def __init__(self, path) -> None:
        super().__init__(path)

    def _init_file(self) -> None:
        content = {
            'euiv_docs_folder':''
        }
        with open(self.path, 'w') as f:
            json.dump(content, f, indent=1)

        return content

    def get_setting(self, setting):
        return self.content.get(setting)
    
    def is_setting_valid(self, setting):
        tests = {
            'euiv_docs_folder': self.content.get(setting).endswith('Europa Universalis IV')
        }
        return tests[setting]
    
    @JSONFile._update_file
    def update_setting(self, setting, new_value):
        if setting in self.content.keys():
            self.content[setting] = new_value
        else:
            raise KeyError(f'Given setting "{setting}" is not a valid setting.')


class ModCollection(JSONFile):
    def __init__(self, path) -> None:
        super().__init__(path)

    def _init_file(self):
        euiv_mods_folder = os.path.join(SETTINGS.get_setting('euiv_docs_folder'),'mod')
        content = {'mods':[],'sets':{},'loaded':None}
        content['mods'] = ['mod/'+file for file in os.listdir(euiv_mods_folder) if '.mod' in file]
        with open(self.path, 'w') as f:
            json.dump(content, f, indent=1)
        return content

    def import_mod(self, mod_zip_file, mod_name):
        euiv_docs_folder = SETTINGS.get_setting('euiv_docs_folder')
        if euiv_docs_folder == "":
            ErrorDialog(self, 'Please set the EUIV documents folder in Settings.')
            return

        euiv_mods_folder = os.path.join(euiv_docs_folder,'mod')
        os.makedirs(euiv_mods_folder, exist_ok=True)
        zipfile.ZipFile(mod_zip_file).extractall(TEMP_FOLDER)
        
        mod_name = mod_name.replace(" ","_")
        if mod_name == "":
            mod_name = os.listdir(TEMP_FOLDER)[0].replace('.mod','')
        else:
            self.rename_mod_files(TEMP_FOLDER, mod_name)
        
        try:
            self.add_mod(mod_name)
        except ValueError:
            ErrorDialog(self, 'Mod name already taken. Please provide a different name.')
            return
            
        ext_mod_file, int_mod_file = self.find_mod_files(TEMP_FOLDER)

        ext_mod_content = ext_mod_file.read()
        ext_mod_content['path'] = os.path.join(euiv_mods_folder, mod_name).replace('\\','/')
        ext_mod_content['remote_file_id'] = mod_name
        ext_mod_file.write(ext_mod_content)

        int_mod_content = int_mod_file.read()
        int_mod_content['path'] = f"mod/{mod_name}"
        int_mod_content['remote_file_id'] = mod_name
        int_mod_file.write(int_mod_content)

        shutil.copytree(TEMP_FOLDER, euiv_mods_folder, dirs_exist_ok=True, copy_function=shutil.move)
        shutil.rmtree(TEMP_FOLDER, ignore_errors=True)

    @staticmethod
    def rename_mod_files(mod_folder, new_name):
        for dirpath, dirnames, filenames in os.walk(mod_folder, topdown=False):
            for filename in filenames:
                if filename.endswith('.mod'):
                    old_path = os.path.join(dirpath, filename)
                    old_filename = os.path.split(old_path)[1].split('.')[0]
                    new_filename = filename.replace(old_filename, new_name)
                    new_path = os.path.join(dirpath, new_filename)
                    shutil.move(old_path, new_path)
            
            if dirpath == mod_folder:
                old_path = os.path.join(dirpath, dirnames[0])
                old_dirname = os.path.split(old_path)[1]
                new_dirname = dirnames[0].replace(old_dirname, new_name)
                new_path = os.path.join(dirpath, new_dirname)
                shutil.move(old_path, new_path)

    @staticmethod
    def find_mod_files(mod_folder):
        for dirpath, _, filenames in os.walk(mod_folder):
            for filename in filenames:
                if filename.endswith('.mod'):
                    file_path = os.path.join(dirpath,filename)
                    if dirpath == mod_folder:
                        ext_mod_file = file_path
                    else:
                        int_mod_file = file_path
        return ModFile(ext_mod_file), ModFile(int_mod_file)

    def delete_mod(self, mod_name):
        euiv_mods_folder = os.path.join(SETTINGS.get_setting('euiv_docs_folder'),'mod')
        mod_file = os.path.join(os.path.join(euiv_mods_folder, mod_name+'.mod'))
        mod_folder = os.path.join(os.path.join(euiv_mods_folder, mod_name))
        os.remove(mod_file)
        shutil.rmtree(mod_folder, ignore_errors=True)

    @staticmethod
    def internal_mod_name(ext_mod_name):
        return f'mod/{ext_mod_name}.mod'
    
    @staticmethod
    def external_mod_name(int_mod_name):
        return int_mod_name.replace('mod/','').replace('.mod','')

    @JSONFile._update_file
    def add_mod(self, mod_name, set_name=None):
        mod_name = self.internal_mod_name(mod_name)
        
        if set_name is None:
            dest = self.content['mods']
        else:
            dest = self.content['sets'][set_name]

        if mod_name in dest:
            raise ValueError
        dest.append(mod_name)

    @JSONFile._update_file        
    def remove_mod(self, mod_name, set_name=None):
        if set_name is None:
            locs = [self.content['mods']] \
                 + [self.content['sets'][set_name] for set_name in self.content['sets'].keys()]
            self.delete_mod(mod_name)
        else:
            locs = [self.content['sets'][set_name]]
            
        mod_name = self.internal_mod_name(mod_name)
        for loc in locs:
            if mod_name in loc:
                loc.remove(mod_name)
    
    @JSONFile._update_file
    def create_set(self, set_name, mods:list):
        if set_name in self.content['sets'].keys():
            raise ValueError
        mods = [self.internal_mod_name(mod) for mod in mods]
        self.content['sets'][set_name] = mods

    @JSONFile._update_file
    def delete_set(self, set_name):
        del self.content['sets'][set_name]

    @JSONFile._update_file
    def load_set(self, set_name):
        euiv_docs_folder = SETTINGS.get_setting('euiv_docs_folder')
        if euiv_docs_folder == "":
            ErrorDialog(self, 'Please set the EUIV documents folder in Settings.')
            return

        dlc_load_path = os.path.join(euiv_docs_folder, 'dlc_load.json')
        if os.path.exists(dlc_load_path):
            with open(dlc_load_path, 'r') as f:
                dlc_load = json.load(f)
        else:
            dlc_load = {'enabled_mods':[], 'disabled_dlcs':[]}

        if set_name is None:
            dlc_load['enabled_mods'] = []
        else:
            dlc_load['enabled_mods'] = self.content['sets'][set_name]

        with open(dlc_load_path, 'w') as f:
            json.dump(dlc_load, f)
        
        self.content['loaded'] = set_name

    def get_mods(self, set_name=None):
        if set_name is None:
            mods = self.content['mods']
        else:
            mods = self.content['sets'][set_name]

        return [self.external_mod_name(mod) for mod in mods]

    def get_sets(self):
        return list(self.content['sets'].keys())
    
    def get_loaded_set(self):
        return self.content['loaded']


class ErrorDialog(wx.MessageDialog):
    def __init__(self, parent, message, 
                 caption="Error", style=wx.OK | wx.ICON_ERROR,
                 *args, **kw):
        super().__init__(parent, message, caption, style, *args, **kw)
        self.ShowModal()
        self.Destroy()


class TextSelector(wx.Panel):
    def __init__(self, parent, desc:str=None, default:str='', hint=None, size=(300,-1), *args, **kw):
        
        super().__init__(parent, size=size, *args, **kw)
        
        if desc is not None:
            desc_text = wx.StaticText(self, label=desc)
        
        self.text_ctrl = wx.TextCtrl(self, value=default)
        if hint is not None: 
            self.text_ctrl.SetHint(hint)

        vbox = wx.BoxSizer(wx.VERTICAL)
        if desc is not None: vbox.Add(desc_text, flag=wx.BOTTOM, border=5)
        vbox.Add(self.text_ctrl, proportion=1, flag=wx.EXPAND)
        self.SetSizer(vbox)
        vbox.Fit(self)
        self.SetSize(size)

    def GetValue(self):
        return self.text_ctrl.GetValue()


class PathSelector(wx.Panel):
    def __init__(self, parent, type:str, desc=None, default='', hint=None, size=(300,-1), *args, **kw):
        super().__init__(parent, size=size, *args, **kw)
        
        if type == 'file':
            self.instr = 'Choose a File'
            self.dialog = wx.FileDialog(self, 'Choose a file', 
                                        wildcard='All files (*.*)|*.*',
                                        style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
        elif type in ['dir','folder']:
            self.instr = 'Choose a Folder'
            self.dialog = wx.DirDialog(self, 'Choose a folder',
                                       style=wx.DD_DEFAULT_STYLE)
        else:
            raise ValueError(f'PathSelector type argument must be either "file" or "dir"/"folder". "{type}" was passed.')

        if desc is not None:
            desc_text = wx.StaticText(self, label=desc)
        
        self.text_ctrl = wx.TextCtrl(self, value=default)
        if hint is not None: 
            self.text_ctrl.SetHint(hint)
        
        self.button = wx.Button(self, label=self.instr)
        self.button.Bind(wx.EVT_BUTTON, self.on_button_press)

        vbox = wx.BoxSizer(wx.VERTICAL)
        if desc is not None: vbox.Add(desc_text, flag=wx.BOTTOM, border=5)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(self.text_ctrl, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10)
        hbox.Add(self.button)
        vbox.Add(hbox, flag=wx.EXPAND)
        self.SetSizer(vbox)
        vbox.Fit(self)
        self.SetSize(size)

    def on_button_press(self, event):
        if self.dialog.ShowModal() == wx.ID_CANCEL:
            return
        self.text_ctrl.SetValue(self.dialog.GetPath())

    def GetValue(self):
        return self.text_ctrl.GetValue()


class CheckListBoxNoSelection(wx.CheckListBox):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.Bind(wx.EVT_LISTBOX, self._unselect)

    def _unselect(self, event):
        self.Deselect(event.GetSelection())


class Mods(wx.Panel): # TODO Re-do with a ListBox, so mods can also be renamed and removed
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        
        self.file_selector = PathSelector(self, 
            type='file',
            hint='mod.zip',
            size=(400,-1),
        )
        self.file_selector.text_ctrl.Bind(wx.EVT_TEXT, self.on_file_selected)
        
        self.name_selector = TextSelector(self,
            hint='Name to give the Mod files (Optional)',
            size=(400,-1)
        )
        
        self.add_button = wx.Button(self, label='Add Mod', size=(91,-1))
        self.add_button.Bind(wx.EVT_BUTTON, self.on_add_mod)

        self.mod_list_box = wx.ListBox(self,
            choices=MOD_COLLECTION.get_mods(),
            size=(200,220)
        )
        self.mod_list_box.Bind(wx.EVT_LISTBOX, self.on_mod_selected)

        self.delete_button = wx.Button(self, label='Delete Mod')
        self.delete_button.Bind(wx.EVT_BUTTON, self.on_delete_mod)

        out_vbox = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add((0,30)) # Top padding
        
        vbox.Add(self.file_selector, proportion=1, flag=wx.BOTTOM | wx.EXPAND, border=10)
        hbox1 = wx.BoxSizer(wx.HORIZONTAL) # name selector & add button
        hbox1.Add(self.name_selector, proportion=1, flag=wx.RIGHT | wx.EXPAND, border=10)
        hbox1.Add(self.add_button)
        vbox.Add(hbox1, flag=wx.BOTTOM, border=30)

        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        hbox2.Add(self.mod_list_box, flag=wx.RIGHT, border=20)
        vbox21 = wx.BoxSizer(wx.VERTICAL)
        vbox21.Add(self.delete_button)
        hbox2.Add(vbox21)
        vbox.Add(hbox2)

        hbox.Add(vbox, flag=wx.RIGHT | wx.LEFT, border=20)
        out_vbox.Add(hbox)
        self.SetSizer(out_vbox)
        out_vbox.Fit(self)

        self.update_button_status([self.add_button, self.delete_button])

    def update_button_status(self, buttons:list[wx.Button]):
        enable_when = {
            self.add_button: self.file_selector.GetValue() != '',
            self.delete_button: self.mod_list_box.GetStringSelection() != ''
        }

        for button in buttons:
            if enable_when[button]:
                button.Enable()
            else:
                button.Disable()

    def on_file_selected(self, event):
        self.update_button_status([self.add_button])

    def on_add_mod(self, event):
        mod_zip = self.file_selector.GetValue()
        mod_name = self.name_selector.GetValue()
        MOD_COLLECTION.import_mod(mod_zip, mod_name)
        self.mod_list_box.Set(MOD_COLLECTION.get_mods())
        self.file_selector.text_ctrl.Clear()
        self.name_selector.text_ctrl.Clear()
        app.sets_page.update_mod_list_box()
        
    def on_mod_selected(self, event):
        self.update_button_status([self.delete_button])
    
    def on_delete_mod(self, event):
        mod_name = self.mod_list_box.GetStringSelection()
        MOD_COLLECTION.remove_mod(mod_name)
        self.mod_list_box.Set(MOD_COLLECTION.get_mods())
        app.sets_page.update_mod_list_box()


class ModSets(wx.Panel):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.selected_set = None

        self.new_set_name_selector = TextSelector(self, 
            hint='New ModSet Name',
            pos=(20,30),
            size=(200,-1)
        )
        self.new_set_name_selector.text_ctrl.Bind(wx.EVT_TEXT, self.on_text_edited)
        self.create_set = wx.Button(self, label='Create', pos=(240,30), size=(200,-1))
        self.create_set.Bind(wx.EVT_BUTTON, self.on_create_set)

        self.set_list_box = wx.ListBox(self, 
            choices=MOD_COLLECTION.get_sets(), 
            pos=(20,80),
            size=(200,220) 
        )
        self.set_list_box.Bind(wx.EVT_LISTBOX, self.on_set_selected)
        
        self.mod_list_box = CheckListBoxNoSelection(self, 
            choices=[], 
            pos=(240,80), 
            size=(200,220),
        )
        self.mod_list_box.Bind(wx.EVT_CHECKLISTBOX, self.on_mod_selected)

        self.set_name_editor = TextSelector(self, 
            hint='Rename the ModSet',
            pos=(20,320),
            size=(200,-1)
        )
        
        self.rename_set = wx.Button(self, label='Rename Set', pos=(240,320), size=(90,-1))
        self.rename_set.Bind(wx.EVT_BUTTON, self.on_rename_set)

        self.delete_set = wx.Button(self, label='Delete Set', pos=(350,320), size=(90,-1))
        self.delete_set.Bind(wx.EVT_BUTTON, self.on_delete_set)

        self.load_set = wx.Button(self, label='Load Set to EUIV', pos=(20,360), size=(100,-1))
        self.load_set.Bind(wx.EVT_BUTTON, self.on_load_set)

        self.unload_set = wx.Button(self, label='Unload', pos=(140,360), size=(80,-1))
        self.unload_set.Bind(wx.EVT_BUTTON, self.on_unload_set)

        self.loaded_set_text = wx.StaticText(self, 
            label=f'Currently loaded: {MOD_COLLECTION.get_loaded_set()}', pos=(240,365)
        )

        self._update_button_status([self.create_set,self.rename_set,self.load_set,self.unload_set])
    
    def _update_button_status(self, buttons):
        enable_when = {
            self.rename_set: self.set_list_box.GetStringSelection() != '',
            self.delete_set: self.set_list_box.GetStringSelection() != '',
            self.load_set: self.set_list_box.GetStringSelection() != '',
            self.unload_set: MOD_COLLECTION.get_loaded_set() is not None,
            self.create_set: self.new_set_name_selector.GetValue() != ''
        }

        for button in buttons:
            if enable_when[button]:
                button.Enable()
            else:
                button.Disable()

    def update_mod_list_box(self):
        self.selected_set = self.set_list_box.GetStringSelection()
        if self.selected_set != '':
            all_mods = MOD_COLLECTION.get_mods()
            set_mods = MOD_COLLECTION.get_mods(self.selected_set)
            self.mod_list_box.Set(all_mods)
            self.mod_list_box.SetCheckedStrings(set_mods)
            self._update_button_status([self.rename_set, self.delete_set, self.load_set])

    def on_text_edited(self, event):
        self._update_button_status([self.create_set])

    def on_set_selected(self, event):
        self.update_mod_list_box()

    def on_mod_selected(self, event):
        mod = event.GetString()
        if self.mod_list_box.IsChecked(event.GetInt()):
            MOD_COLLECTION.add_mod(mod, set_name=self.selected_set)
        else:
            MOD_COLLECTION.remove_mod(mod, set_name=self.selected_set)
        
        if self.selected_set == MOD_COLLECTION.get_loaded_set():
            MOD_COLLECTION.load_set(self.selected_set)

    def on_create_set(self, event):
        set_name = self.new_set_name_selector.GetValue()
        
        try:
            MOD_COLLECTION.create_set(set_name, [])
        except ValueError:
            ErrorDialog(self, 'ModSet name already taken. Please provide a different name.')
            return
        
        self.new_set_name_selector.text_ctrl.SetValue('')
        self.set_list_box.Set(MOD_COLLECTION.get_sets())
        self.set_list_box.SetStringSelection(set_name)
        self.on_set_selected(wx.EVT_LISTBOX)

    def on_rename_set(self, event):
        mods = list(self.mod_list_box.GetCheckedStrings())

        MOD_COLLECTION.delete_set(self.selected_set)
        
        new_name = self.set_name_editor.GetValue()
        MOD_COLLECTION.create_set(new_name, mods)

        self.selected_set = new_name
        self.set_name_editor.text_ctrl.SetLabelText('')
        self.set_list_box.Set(MOD_COLLECTION.get_sets())
        self.set_list_box.SetStringSelection(new_name)

    def on_delete_set(self, event):
        MOD_COLLECTION.delete_set(self.selected_set)
        self.set_list_box.Set(MOD_COLLECTION.get_sets())
        self.mod_list_box.Set([])
        self._update_button_status([self.rename_set, self.delete_set, self.load_set])

    def on_load_set(self, event):
        MOD_COLLECTION.load_set(self.selected_set)
        self.loaded_set_text.SetLabelText(f'Currently loaded: {self.selected_set}')
        self._update_button_status([self.unload_set])
    
    def on_unload_set(self, event):
        MOD_COLLECTION.load_set(None)
        self.loaded_set_text.SetLabelText(f'Currently loaded: {None}')
        self._update_button_status([self.unload_set])


class SettingsTab(wx.Panel):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        euiv_docs_folder = PathSelector(
            parent=self,
            type='dir', 
            desc='Select the EUIV documents folder.',
            default=SETTINGS.get_setting('euiv_docs_folder'),
            pos=(20,30),
            size=(420,-1)
        )
        euiv_docs_folder.text_ctrl.Bind(
            wx.EVT_TEXT, 
            partial(self.on_setting_update, setting='euiv_docs_folder')
        )

    def on_setting_update(self, event, setting):
        text_ctrl_obj = event.GetEventObject()        
        SETTINGS.update_setting(setting, text_ctrl_obj.GetValue())


class SettingsSetup(wx.Dialog):
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.SetTitle('Startup Configuration')
        self.Center()
        vbox = wx.BoxSizer(wx.VERTICAL)

        text = wx.StaticText(self, 
            label='Please confirm the EUIV documents folder. This can be changed later.',
        )
        vbox.Add(text, flag=wx.TOP | wx.ALIGN_CENTER, border=20)
        
        self.euiv_docs_folder_selector = PathSelector(self,
            type='dir',
            desc='',
            default=f"{os.path.join(os.path.expanduser('~'),'Documents','Paradox Interactive','Europa Universalis IV')}",
            size=(450,50)
        )
        vbox.Add(self.euiv_docs_folder_selector, flag=wx.ALL, border=20)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        ok_button = wx.Button(self, label='Ok')
        ok_button.Bind(wx.EVT_BUTTON, self.on_ok_pressed)
        hbox.Add(ok_button, flag=wx.BOTTOM, border=20)
        vbox.Add(hbox, flag=wx.ALIGN_CENTER)

        self.Bind(wx.EVT_CLOSE, lambda x: exit())

        self.SetSizer(vbox)
        vbox.Fit(self)

    def on_ok_pressed(self, event):
        if 'Europa Universalis IV' in self.euiv_docs_folder_selector.GetValue():
            self.EndModal(wx.ID_OK)
        else:
            self.EndModal(wx.ID_CANCEL)

    def get_setting(self):
        return self.euiv_docs_folder_selector.GetValue()


class EUIVModManager(wx.App):
    def OnInit(self):
        return True
    
    def build(self):
        frame = wx.Frame(parent=None, title='EUIV Mod Manager', size=(-1,-1))
        frame.SetSize(485,500)
        frame.Center()
        frame.SetWindowStyle(wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX))
        
        notebook = wx.Notebook(frame)

        mods_page = Mods(notebook)
        self.sets_page = ModSets(notebook)
        settings_page = SettingsTab(notebook)

        notebook.AddPage(mods_page, 'Add Mod')
        notebook.AddPage(self.sets_page, 'ModSets')
        notebook.AddPage(settings_page, 'Settings')

        frame.Show()
    

def main():
    global app, TEMP_FOLDER, SETTINGS, MOD_COLLECTION

    app = EUIVModManager()

    TEMP_FOLDER = os.path.abspath('./temp/')
    SETTINGS = UserSettings('./settings.json')
    
    while not SETTINGS.is_setting_valid('euiv_docs_folder'):
        setup = SettingsSetup(None)
        if setup.ShowModal() == wx.ID_OK:
            SETTINGS.update_setting('euiv_docs_folder', setup.get_setting())
        else:
            ErrorDialog(None, 'The selected EUIV documents folder is not valid. Please select a valid folder.')
        setup.Destroy()

    MOD_COLLECTION = ModCollection('./collection.json')

    app.build()
    app.MainLoop()


if __name__ == '__main__':
    main()
