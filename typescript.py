import sublime
# from sublime_plugin import WindowCommand
from sublime_plugin import TextCommand
from sublime_plugin import EventListener
from subprocess import Popen, PIPE
from queue import Queue
from threading import Thread
import os
import json
import time


# http://www.eladyarkoni.com/2012/09/sublime-text-auto-complete-plugin.html

TSS_PATH = os.path.join(os.path.dirname(__file__),'bin', 'tss.js')


# 1. on update: update nocheck, completions, immediately
# 2. 
# 3. 

class TypescriptProjectManager(object):

    def __init__(self):
        self.services = {}

    # returns an initializes a project given a certain view
    def service(self, view):
        window_id = str(view.window().id())
        if window_id in self.services:
            return self.services[window_id]

        service = TypescriptToolService(window_id)

        file = view.settings().get("typescript_root")
        if file:
            project_file = view.window().project_file_name()
            file_path = os.path.join(os.path.dirname(project_file), file)
            # TODO save that file_path somewhere for building
            service.initialize(file_path)

        self.services[window_id] = service
        return service

        # if it specifies a root file, use that




 


projects = TypescriptProjectManager()

class TypescriptToolService(object):
    
    def __init__(self, service_id):
        # print("TypescriptToolService()", service_id)
        self.service_id = service_id
        self.process = None
        self.errors = []
        self.loaded = False
        self.completions = []
        self.tools = None

    def is_initialized(self):
        return self.process != None

    def initialize(self, root_file_path):
        # can only initialize once
        # print("initialize", self.service_id, root_file_path)
        self.loaded = False        

        # kwargs = {}
        # self.process = Popen(["/usr/local/bin/node", TSS_PATH, root_file_path], stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)
        self.tools = ToolsBridgeNow(self.service_id)
        self.tools.connect(root_file_path)


    # Only allow you to start once for now? 
    def start(self, file_path):
        return
        self.initialize(file_path)


    def on_loaded(self, message):
        # print("on_loaded", self.service_id)
        self.loaded = True
        self.check_errors()
        if (self.delegate):
            self.delegate.on_typescript_loaded()

    def check_errors(self):
        return
        # print("check_errors", self.service_id, self.writer.service_id)
        self.tools.add('showErrors', self.on_errors)

    def on_errors(self, error_infos):
        self.errors = list(map(lambda e: Error(e), error_infos))
        if (self.delegate):
            self.delegate.on_typescript_errors(self.errors)

    def add_file(self, view):
        # print("add_file", self.service_id, view.file_name())
        # don't check errors here?
        if (self.is_initialized()):
            if (self.loaded):
                self.update_file(view)
                self.check_errors()

        else:
            self.initialize(view.file_name())
            self.check_errors()

    # automatically runs checkerrors
    def update_file(self, view):
        (lineCount, col) = view.rowcol(view.size())
        content = view.substr(sublime.Region(0, view.size()))
        print("update_file", self.service_id, view.file_name())
        # write these immediately
        
        self.tools.write('update nocheck {0} {1}'.format(str(lineCount+1),view.file_name().replace('\\','/')))
        self.tools.write(content)
        message = self.tools.read()

    def list_files(self):
        self.writer.add('files')
        self.reader.next_data(self.on_list_files)

    def on_list_files(self, files):
        if self.delegate:
            self.delegate.on_typescript_files(files)


    def load_completions(self, is_member, line, pos, file):
        member_out = str(is_member).lower()
        self.tools.write('completions {0} {1} {2} {3}'.format(member_out, str(line+1), str(pos+1), file))
        complete_data = self.tools.read()
        # print("Read! ", complete_data)
        self.on_completions(complete_data)

    def on_completions(self, data):
        if data and 'entries' in data:
            entries = data['entries']
            print("COMPLETIONS", entries)
            self.completions = list(map(lambda c: Completion(c), data['entries']))
        else:
            print("!!! Completions")

 




class ToolsBridgeNow(object):
    def __init__(self, service_id):
        self.service_id = service_id
        self.process = None

    def connect(self, root_file_path):
        kwargs = {}
        self.process = Popen(["/usr/local/bin/node", TSS_PATH, root_file_path], stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)
        self.stdin = self.process.stdin
        self.stdout = self.process.stdout
        loaded = self.read() # swallow the loaded response
        print("LOADED")

    def write(self, command):
        print("TOOLS-" + self.service_id + " (write)", command.partition("\n")[0])            
        self.stdin.write(bytes(command+'\n','UTF-8'))

    def read(self):
        line = self.stdout.readline().decode('UTF-8')
        print("TOOLS-" + self.service_id + " (read)", line.partition("\n")[0])            
        data = json.loads(line)
        return data        










# class ToolsBridge(object):
    
#     def __init__(self, service_id):
#         self.service_id = service_id

#     def connect(self, process, on_loaded):
#         self.writer = ToolsWriter(process.stdin, self.service_id)
#         self.writer.start()

#         self.reader = ToolsReader(process.stdout, self.service_id)
#         self.reader.add(on_loaded) # need to consume the "loaded" response
#         self.reader.start()

#     def add(self, message, on_data):
#         self.writer.add(message)
#         self.reader.add(on_data)
#         # you want to do it synchronously, no?
#         # hmm... 


# class ToolsWriter(Thread):

#     def __init__(self, stdin, service_id):
#         Thread.__init__(self)
#         self.stdin = stdin        
#         self.daemon = True
#         self.service_id = service_id
#         self.queue = Queue()

#     def add(self, message):
#         self.queue.put(message)

#     def write_sync(self, command):
#         print("TOOLS-" + self.service_id + " (write)", command.partition("\n")[0])            
#         self.stdin.write(bytes(command+'\n','UTF-8'))

#     def run(self):
#         for command in iter(self.queue.get, None):
#             self.write_sync(command)
#         self.stdin.close()

# class ToolsReader(Thread):

#     # have an ARRAY of handlers, one should get called per line, or you throw an error

#     def __init__(self, stdout, service_id):
#         Thread.__init__(self)
#         self.stdout = stdout
#         self.daemon = True
#         self.service_id = service_id
#         self.line_handlers = Queue() 

#     def add(self, handler):
#         self.line_handlers.put(handler, False) # don't block

#     def read_sync(self):
#         line = self.stdout.readline().decode('UTF-8')
#         print("TOOLS-" + self.service_id + " (read)", line.partition("\n")[0])            
#         data = json.loads(line)
#         return data

#     def run(self):
#         for data in iter(self.read_sync, b''):
#             on_data = self.line_handlers.get(False) # don't block
#             on_data(data)

#         self.stdout.close()



# class TypescriptStartCommand(TextCommand):
#     def run(self, edit):
#         service = projects.service(self.view)
#         service.start(self.view.file_name())
#         service.delegate = self
#         self.wait_for_load(service)

#     def is_enabled(self):
#         return isTypescript(self.view)

#     def on_typescript_errors(self, errors):
#         self.display_errors(errors)

#     def on_typescript_loaded(self):
#         service = projects.service(self.view)
#         service.check_errors()        

#     def display_errors(self,errors):
#         self.view.set_status("typescript", "Typescript [%s ERRORS]" % len(errors))
#         render_errors(self.view, errors)

#     def wait_for_load(self, service, i=0, dir=1):
#         # self.display_errors(service.errors)
#         if not service.loaded:
#             before = i % 8
#             after = (7) - before
#             if not after:
#                 dir = -1
#             if not before:
#                 dir = 1
#             i += dir
#             self.view.set_status("typescript", 'Typescript Loading [%s=%s]' % (' ' *before, ' '*after))
#             sublime.set_timeout(lambda: self.wait_for_load(service, i, dir), 100)




def render_errors(view, errors):
    file = view.file_name()
    # print("RENDER_ERRORS", len(errors), file)
    matching_errors = [e for e in errors if e.file == file]
    regions = list(map(lambda e: error_region(view, e), matching_errors))
    view.add_regions('typescript-error', regions, 'invalid', 'cross', sublime.DRAW_NO_FILL | sublime.DRAW_NO_OUTLINE | sublime.DRAW_SOLID_UNDERLINE)

def render_error_status(view, errors):
    sel = view.sel()
    (line, col) = view.rowcol(sel[0].begin())
    line_error = find_error(errors, line, view.file_name())
    if line_error:
        view.set_status("typescript", line_error.text)    
    else:
        view.erase_status("typescript")


def error_region(view, error):
    a = view.text_point(error.start.line-1, error.start.character-1)
    b = view.text_point(error.end.line-1, error.end.character-1)
    return sublime.Region(a, b)

def find_error(errors, line, file):
    for error in errors:
        if error.file == file and (line+1 >= error.start.line and line+1 <= error.end.line):
            return error
    return None



# shows the currently indexed files (mostly for debugging, but you could use it to jump to ONLY typescript files if you wanted
class TypescriptShowFilesCommand(TextCommand):

    def run(self, edit):
        service = projects.service(self.view)
        service.delegate = self
        service.list_files()

    def on_typescript_files(self, files):
        # ignore the files added by tss.js
        bin_path = os.path.join("sublime-typescript", "bin")
        self.files = [file for file in files if not bin_path in file]
        items = list(map(lambda f: [os.path.basename(f), os.path.dirname(f)], self.files))
        sublime.active_window().show_quick_panel(items, self.on_select_panel_item)

    def on_select_panel_item(self, index):
        if index < 0: return
        file = self.files[index]
        sublime.active_window().open_file(file)

 
# AUTO COMPLETION
# class TypescriptComplete(TextCommand):
#     def run(self, edit, characters):
#         print("TYPESCRIPT COMPLETE!")
#         for region in self.view.sel():
#             self.view.insert(edit, region.end(), characters)
#         self.view.run_command('auto_complete',{
#             'disable_auto_insert': True,
#             'api_completions_only': True,
#             'next_competion_if_showing': True
#         })



class TypescriptEventListener(EventListener):

    DIRTY_DELAY = 300

    def __init__(self):
        self.view_modified_time = 0

    # called whenever a veiw is focused
    def on_activated_async(self,view):
        # print("on_activated_async", view.file_name())
        if not is_typescript(view): 
            self.current_view = None
            return
        
        self.current_view = view
        service = projects.service(view)
        # print(" - service", service.service_id)
        service.delegate = self
        service.add_file(view)
        # if it is a typescript file, and we aren't loaded, run LOAD synchronously. Just burn through it fast

    def on_clone_async(self,view):
        return
        # print("on_clone_async")

    def init_view(self,view):
        return
        # print("init_view")

    def on_load_async(self, view):
        return
        # print("on_load_async")


    def on_typescript_loaded(self):
        return

    # # called on each character sent
    def on_modified_async(self, view):
        if not is_typescript(view): return
        # self.mark_view_dirty(view)

        service = projects.service(self.current_view)
        service.update_file(self.current_view)
        service.delegate = self


        # load auto completions too
        # service = projects.service(view)

        # print("on_modified_async")

    def mark_view_dirty(self, view):
        dirty_time = time.time()
        # print("mark_view_dirty", dirty_time)        
        self.current_view = view
        self.view_modified_time = dirty_time
        # in delay milliseconds, check to see if the view has been changed... again
        # only run update_file if it hasn't been called again since
        sublime.set_timeout(lambda: self.check_update_file(dirty_time), self.DIRTY_DELAY)

    def check_update_file(self, dirty_time):
        if self.view_modified_time == dirty_time:        
            service = projects.service(self.current_view)
            # service.update_file(self.current_view)
            service.check_errors()
            service.delegate = self

    def on_typescript_errors(self, errors):
        if self.current_view:
            render_errors(self.current_view, errors)
        
    # # called a lot when selecting, AND each character
    def on_selection_modified_async(self, view):
        if not is_typescript(view): return

        service = projects.service(view)
        render_error_status(view, service.errors)


    # def on_post_save_async(self,view):
    #     print("on_post_save_async")


    # def handle_timeout(self,view):
    #     self.pending = self.pending -1
    #     if self.pending == 0:
    #         TSS.errors(view)

    def on_query_completions(self, view, prefix, locations):
        if not is_typescript(view): return

        service = projects.service(view)

        pos = view.sel()[0].begin()
        (line, col) = view.rowcol(pos)
        is_member = True        
        service.load_completions(is_member, line, col, view.file_name())
        entries = service.completions
        print("QUERY COMPLETIONS", entries)
        completions = list(map(self.entry_completion, entries))

        return completions

    def entry_completion(self, entry):
        # [{"name":"fullName","kind":"function","kindModifiers":"export","type":"(first: string, last: string): string","fullSymbolName":"File.fullName","docComment":""}],"prefix":"ful"}
        return (entry.name, entry.name)
                    
    # def on_query_context(self, view, key, operator, operand, match_all):
    #     if key == "typescript":
    #         view = sublime.active_window().active_view()
    #         return is_ts(view)        


def is_typescript(view=None):
    if view is None:
        view = sublime.active_window().active_view()
    return 'source.ts' in view.scope_name(0)

def plugin_loaded():
    #settings = sublime.load_settings('typescript.sublime-settings')
    #print("TS Loaded", settings)
    print("Typescript: Loaded")


class Completion(object):
    def __init__(self, dict):
        self.name = dict['name']
        self.type = dict['type']
        self.comment = dict['docComment']

class Error(object):
    def __init__(self, dict):
        self.file = dict['file']
        self.start = ErrorPosition(dict['start'])
        self.end = ErrorPosition(dict['end'])
        self.text = dict['text']
        self.phase = dict['phase']
        self.category = dict['category']

class ErrorPosition(object):
    def __init__(self, dict):
        self.line = dict['line']
        self.character = dict['character']    
