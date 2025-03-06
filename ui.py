import tkinter as tk
from os import path
from functools import partial

class MainUi:
    ROWS = 25
    iconDir = path.join(path.dirname(__file__), "icons")

    def __init__(self, config):
        self.row = 0
        self.icons = {}
        self.icons['left_arrow'] = tk.PhotoImage(file=path.join(self.iconDir, "left_arrow.gif"))
        self.icons['right_arrow'] = tk.PhotoImage(file=path.join(self.iconDir, "right_arrow.gif"))
        self.rows = None
        self.subscribers = {}
        self.config = config
        self.title = None
        self.station = None
        self.bind_btn = None
        self.prev_btn = None
        self.next_btn = None
        
    def nextRow(self):
        self.row+=1

    def plugin_app(self, parent:tk.Widget) -> tk.Widget:
        self.frame = tk.Frame(parent)
        
        frame = tk.Frame(self.frame)
        frame.columnconfigure(1, weight=1)
        frame.grid(row=0, column=0, sticky=tk.EW)

        self.prev_btn = tk.Label(frame, image=self.icons['left_arrow'], cursor="hand2")
        self.prev_btn.bind("<Button-1>", partial(self.event, "prev"))
        self.prev_btn.grid(row=0, column=0, sticky=tk.W)
        self.title = tk.Label(frame, text="Total")
        self.title.grid(row=0, column=1, sticky=tk.EW)
        
        self.next_btn = tk.Label(frame, image=self.icons['right_arrow'], cursor="hand2")
        self.next_btn.bind("<Button-1>", partial(self.event, "next"))
        self.next_btn.grid(row=0, column=2, sticky=tk.E)

        self.station = tk.Label(frame, text="Station")
        self.station.grid(row=1, column=0, sticky=tk.EW, columnspan=3)
        
        self.bind_btn = tk.Button(frame, text="Bind this construction with docked station", command=partial(self.event, "bind", None))
        self.bind_btn.grid(row=2, column=0, sticky=tk.EW, columnspan=3)

        frame = tk.Frame(self.frame)
        frame.columnconfigure(3, weight=1)
        frame.grid(row=1, column=0, sticky=tk.EW)

        tk.Label(frame, text="Commodity").grid(row=0, column=0)
        tk.Label(frame, text="Need").grid(row=0, column=1)
        tk.Label(frame, text="Cargo").grid(row=0, column=2)
        tk.Label(frame, text="FleetCarrier").grid(row=0, column=3)

        self.rows = list()
        for i in range(self.ROWS):
            labels = {}
            labels['name'] = tk.Label(frame, text=i)
            labels['name'].grid(row=i+1, column=0)
            labels['needed'] = tk.Label(frame, text="b")
            labels['needed'].grid(row=i+1, column=1)
            labels['cargo'] = tk.Label(frame, text="c")
            labels['cargo'].grid(row=i+1, column=2)
            labels['carrier'] = tk.Label(frame, text="c")
            labels['carrier'].grid(row=i+1, column=3)
            self.rows.append(labels)

        return self.frame
    
    def event(self, event, tkEvent):
        if event in self.subscribers:
            self.subscribers[event](tkEvent)

    def on(self, event, function):
        self.subscribers[event] = function

    def setTitle(self, title):
        if self.title:
            self.title['text'] = title

    def setTable(self, table):
        if not self.rows:
            return
        row = 0
        for i in table:
            if i['needed'] <= 0:
                continue
            #if i['need']-i['carrier'] <= 0:
            #    continue
            if (row >= self.ROWS):
                break

            self.rows[row]['name']['text'] = i['commodityName']

            toBuy = i['needed']-i['cargo']-i['carrier']
            if (i['cargo'] > 0 or i['carrier'] > 0):
                self.rows[row]['needed']['text'] = "{} ({})".format(i['needed'], toBuy)
            else:
                self.rows[row]['needed']['text'] = i['needed']
            self.rows[row]['cargo']['text'] = i['cargo']
            self.rows[row]['carrier']['text'] = i['carrier']

            self.rows[row]['name'].grid(row=row+1, column=0)
            self.rows[row]['needed'].grid(row=row+1, column=1)
            self.rows[row]['cargo'].grid(row=row+1, column=2)
            self.rows[row]['carrier'].grid(row=row+1, column=3)
            
            if (toBuy <= 0):
                self.rows[row]['name']['fg'] = 'green'
                self.rows[row]['needed']['fg'] = 'green'
                self.rows[row]['cargo']['fg'] = 'green'
                self.rows[row]['carrier']['fg'] = 'green'
            else:
                #if i['item'] in this.commodities:
                #    self.rows[row]['name']['fg'] = '#FFF'
                #else:
                #    self.rows[row]['name']['fg'] = config.get_str('dark_text')
                self.rows[row]['name']['fg'] = self.config.get_str('dark_text')
                self.rows[row]['needed']['fg'] = self.config.get_str('dark_text')
                self.rows[row]['cargo']['fg'] = self.config.get_str('dark_text')
                self.rows[row]['carrier']['fg'] = self.config.get_str('dark_text')
            row+=1

        for i in range(row, self.ROWS):
            self.rows[i]['name'].grid_remove()
            self.rows[i]['needed'].grid_remove()
            self.rows[i]['cargo'].grid_remove()
            self.rows[i]['carrier'].grid_remove()

    def setStation(self, station, color=None):
        if self.station:
            self.station['text'] = str(station)
            if color:
                self.station['fg'] = color
            else:
                self.station['fg'] = self.config.get_str('dark_text')