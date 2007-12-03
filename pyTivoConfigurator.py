from Tkinter import *
import ConfigParser

class pyTivoConfigurator(Frame):

        section = None
        
        def buildContainerList(self):
            frame = Frame(self)
            frame.pack(fill=BOTH, expand=1)
            scrollbar = Scrollbar(frame, orient=VERTICAL)
            self.container_list = Listbox(frame, yscrollcommand=scrollbar.set)
            scrollbar.config(command=self.container_list.yview)
            scrollbar.pack(side=RIGHT, fill=Y)
            self.container_list.pack(side=LEFT, fill=BOTH, expand=1)
            self.container_list.bind("<Double-Button-1>", self.selected)

        def selected(self, e):
            if not self.container_list.curselection(): 
                return
            index = self.container_list.curselection()[0]
            self.section = self.container_list.get(index)

            self.updatePath()

        def buildButtons(self):
            frame = Frame(self)
            frame.pack(fill=X)

            save_button = Button(frame, text="Save", command=self.save)
            save_button.pack(side=RIGHT)

            add_button = Button(frame, text="Add", command=self.add)
            add_button.pack(side=RIGHT)

            restart_button = Button(frame, text="Restart pyTivo", command=self.restart)
            restart_button.pack(side=RIGHT)

        def save(self):
            self.writeConfig()

        def add(self):
            import tkSimpleDialog
            sharename = tkSimpleDialog.askstring('Add share', 'Share Name')
            self.config.add_section(sharename)
            self.config.set(sharename, 'type', 'video')
            self.config.set(sharename, 'path', '<Pick A Path>')

            self.updateContainerList()

        def restart(self):
            import win32serviceutil
            self.writeConfig()
            win32serviceutil.RestartService('pyTivo')

        def buildPath(self):
            frame = Frame(self)
            frame.pack(fill=X)
            l = Label(frame, text="Path")
            l.pack(side=LEFT)

            button = Button(frame, text="Browse", command=self.setPath)
            button.pack(side=RIGHT)

            self.path = Entry(frame)
            self.path.pack(side=RIGHT, fill=X, expand=1)


        def setPath(self):
            if not self.section:
                return
            import tkFileDialog
            dir = tkFileDialog.askdirectory()
            
            self.config.set(self.section, 'path', dir)
            self.updatePath()
            
        def updatePath(self):
            if not self.section or not self.config.get(self.section, 'path'):
                return

            self.path.delete(0, END)
            self.path.insert(0, self.config.get(self.section, 'path'))

        def updateContainerList(self):
            self.container_list.delete(0, END)
            for section in self.config.sections():
                if not section == 'Server':
                    self.container_list.insert(END, section)

        def readConfig(self):
            self.config = ConfigParser.ConfigParser()
            self.config.read(self.config_file)

        def writeConfig(self):
            self.config.write(open(self.config_file, 'w'))

        def __init__(self, master=None):
            Frame.__init__(self, master)
            self.master.title('pyTivoConfigurator')
            self.pack(fill=BOTH, expand=1)

            import os
            p = os.path.dirname(__file__)
            self.config_file = os.path.join(p, 'pyTivo.conf')

            self.readConfig()

            self.buildContainerList()
            self.buildPath()
            self.buildButtons()

            self.updateContainerList()



if __name__ == '__main__':
    root = Tk()
    app = pyTivoConfigurator(master=root)
    app.mainloop()
