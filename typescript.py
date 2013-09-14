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


TSS_PATH = os.path.join(os.path.dirname(__file__),'bin', 'tss.js')


# you don't actually have to update the file when you switch tabs...
# only if it hasn't been loaded yet, right?

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

    def is_initialized(self):
        return self.process != None

    def initialize(self, root_file_path):
        # can only initialize once
        # print("initialize", self.service_id, root_file_path)

        self.loaded = False        

        kwargs = {}
        self.process = Popen(["/usr/local/bin/node", TSS_PATH, root_file_path], stdin=PIPE, stdout=PIPE, stderr=PIPE, **kwargs)
        self.writer = ToolsWriter(self.process.stdin, self.service_id)
        self.writer.start()

        # but it's still kind of like... subscribe to the NEXT one
        self.reader = ToolsReader(self.process.stdout, self.service_id)
        self.reader.next_message(self.on_loaded)
        self.reader.start()

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
        # print("check_errors", self.service_id, self.writer.service_id)
        self.writer.add('showErrors')
        self.reader.next_data(self.on_errors)

    def on_errors(self, error_infos):
        self.errors = list(map(lambda e: Error(e), error_infos))
        if (self.delegate):
            self.delegate.on_typescript_errors(self.errors)

    def add_file(self, view):
        # print("add_file", self.service_id, view.file_name())
        if (self.is_initialized()):
            if (self.loaded):
                self.update_file(view)
        else:
            self.initialize(view.file_name())

    # automatically runs checkerrors
    def update_file(self, view):
        (lineCount, col) = view.rowcol(view.size())
        content = view.substr(sublime.Region(0, view.size()))
        # print("update_file", self.service_id, view.file_name())
        self.writer.add('update nocheck {0} {1}'.format(str(lineCount+1),view.file_name().replace('\\','/')))
        self.writer.add(content)
        self.reader.next_message(lambda m: self.check_errors())

    def list_files(self):
        self.writer.add('files')
        self.reader.next_data(self.on_list_files)

    def on_list_files(self, files):
        if self.delegate:
            self.delegate.on_typescript_files(files)



class ToolsWriter(Thread):

    def __init__(self, stdin, service_id):
        Thread.__init__(self)
        self.stdin = stdin        
        self.daemon = True
        self.service_id = service_id
        self.queue = Queue()

    def add(self, message):
        self.queue.put(message)

    def run(self):
        for command in iter(self.queue.get, None):
            print("TOOLS-" + self.service_id + " (write)", command.splitlines()[0])            
            self.stdin.write(bytes(command+'\n','UTF-8'))
        self.stdin.close()

class ToolsReader(Thread):

    def __init__(self, stdout, service_id):
        Thread.__init__(self)
        self.stdout = stdout
        self.daemon = True
        self.service_id = service_id

    def next_data(self, handler):
        self.on_data = handler

    def next_message(self, handler):
        self.on_message = handler

    def run(self):
        for line in iter(self.stdout.readline, b''):
            line = line.decode('UTF-8')
            print("TOOLS-" + self.service_id + " (read)", line.splitlines()[0])            
            data = json.loads(line)
            if line.startswith('"'):
                if self.on_message:
                    self.on_message(data)
                    self.on_message = None    
                else:
                    print(" -- no handler")

            elif self.on_data:
                self.on_data(data)
                self.on_data = None

        self.stdout.close()




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






class TypescriptEventListener(EventListener):

    DIRTY_DELAY = 300

    def __init__(self):
        self.view_modified_time = 0

    # called whenever a veiw is focused
    def on_activated_async(self,view):
        # print("on_activated_async", view.file_name())
        if not isTypescript(view): 
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
        if not isTypescript(view): return
        self.mark_view_dirty(view)
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
            service.update_file(self.current_view)
            service.delegate = self

    def on_typescript_errors(self, errors):
        if self.current_view:
            render_errors(self.current_view, errors)
        
    # # called a lot when selecting, AND each character
    def on_selection_modified_async(self, view):
        if not isTypescript(view): return

        service = projects.service(view)
        render_error_status(view, service.errors)


    # def on_post_save_async(self,view):
    #     print("on_post_save_async")

    
        

    # def handle_timeout(self,view):
    #     self.pending = self.pending -1
    #     if self.pending == 0:
    #         TSS.errors(view)


    # def on_query_completions(self, view, prefix, locations):
    #     if is_ts(view):
    #         pos = view.sel()[0].begin()
    #         (line, col) = view.rowcol(pos)
    #         is_member = str(is_member_completion(view.substr(sublime.Region(view.line(pos-1).a, pos)))).lower()
    #         TSS.complete(view,line,col,is_member)

    #         return COMPLETION_LIST


    # def on_query_context(self, view, key, operator, operand, match_all):
    #     if key == "typescript":
    #         view = sublime.active_window().active_view()
    #         return is_ts(view)        


def isTypescript(view=None):
    if view is None:
        view = sublime.active_window().active_view()
    return 'source.ts' in view.scope_name(0)

def plugin_loaded():
    settings = sublime.load_settings('typescript.sublime-settings')
    print("TS Loaded", settings)
    # sublime.set_timeout(lambda:init(sublime.active_window().active_view()), 300)


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
