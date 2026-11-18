"""Tiny Tapeout MicroPython SDK driver. Select the project before construction."""


class Vec8:
    def __init__(self, board):
        self.board = board
        board.clock_project_stop()
        board.uio_oe_pico.value = 255
        board.uio_in.value = 0
        board.ui_in.value = 0
        board.reset_project(True)
        board.clock_project_once()
        board.reset_project(False)

    def command(self, opcode, data=0, lane=0):
        self.board.uio_in.value = opcode << 5 | lane
        self.board.ui_in.value = data & 255
        self.board.clock_project_once()

    def result(self, lane):
        value = 0
        for byte in range(4):
            self.board.uio_in.value = byte << 3 | lane
            value |= int(self.board.uo_out.value) << (byte * 8)
        return value - (1 << 32) if value & (1 << 31) else value

    def self_test(self):
        self.command(5)
        for lane in range(8):
            self.command(1, lane - 4, lane)
        self.command(3, -128)
        self.command(0)
        for lane in range(8):
            assert self.result(lane) == (lane - 4) * -128
