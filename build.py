#!/usr/bin/env python3
# Hand-assembled x86-64 Linux snake. No compiler, no assembler, no libc.
# Every instruction below is raw machine code written as hex by hand.
# This script only concatenates bytes and resolves label distances.
#
# Memory: one RWX PT_LOAD at 0x400000. rbx = 0x401000 = state base (bss).
#   +00 hx  +04 hy  +08 dx  +0C dy  +10 ndx  +14 ndy  +18 len  +1C food
#   +20 rng +24 score  +28 timespec{sec,nsec}  +38 inbuf[16]  +48 head idx
#   +80 termios orig   +C0 termios raw   +100 grid (30x14 words, TTL)  +500 outbuf
import struct, sys

BASE = 0x400000
W, H = 30, 14
prog = []          # items: bytes | ('L', name) | ('r8'|'r32'|'a32', name)
def L(n): prog.append(('L', n))
def B(h): prog.append(bytes.fromhex(h))
def r8(n): prog.append(('r8', n))
def r32(n): prog.append(('r32', n))
def a32(n): prog.append(('a32', n))

def sys_write(label, n):
    B('B8 01000000'); B('BF 01000000'); B('BE'); a32(label)
    B('BA' + struct.pack('<I', n).hex()); B('0F05')

# ---------------- _start ----------------
B('BB 00104000')                 # mov ebx, 0x401000
B('C7 43 30 000E2707')           # mov dword [rbx+30h], 120000000 (tick)
B('B8 10000000 31FF BE 01540000 8D 93 80000000 0F05')   # ioctl(0,TCGETS,orig)
B('B8 10000000 31FF BE 01540000 8D 93 C0000000 0F05')   # ioctl(0,TCGETS,raw)
B('83 A3 CC000000 F4')           # and [raw.c_lflag], ~(ISIG|ICANON|ECHO)
B('66 C7 83 D6000000 0000')      # VTIME=0, VMIN=0 (non-blocking read)
B('B8 10000000 31FF BE 02540000 8D 93 C0000000 0F05')   # ioctl(0,TCSETS,raw)
sys_write('s_init', 10)          # hide cursor, clear screen
B('0F31 83C801 89 43 20')        # rdtsc; or eax,1; mov [rng],eax
B('C7 43 00 05000000')           # hx = 5
B('C7 43 04 07000000')           # hy = 7
B('C7 43 08 01000000')           # dx = 1
B('C7 43 10 01000000')           # ndx = 1
B('C7 43 18 03000000')           # len = 3
B('E8'); r32('place_food')

L('main_loop')
B('B8 23000000 8D 7B 28 31F6 0F05')          # nanosleep(&ts, 0)
L('read_more')
B('31C0 31FF 8D 73 38 BA 10000000 0F05')     # read(0, inbuf, 16)
B('85C0 0F8E'); r32('input_done')            # test eax,eax; jle
B('89C1 8D 73 38')                           # ecx = n; esi = inbuf
L('key_loop')
B('0FB6 06 FFC6')                            # movzx eax,byte[rsi]; inc esi
B('3C 71 0F84'); r32('quit')                 # 'q'
B('3C 51 0F84'); r32('quit')                 # 'Q'
B('3C 03 0F84'); r32('quit')                 # Ctrl-C
B('3C 77 74'); r8('up');    B('3C 41 74'); r8('up')     # w / ESC[A
B('3C 73 74'); r8('down');  B('3C 42 74'); r8('down')   # s / ESC[B
B('3C 64 74'); r8('right'); B('3C 43 74'); r8('right')  # d / ESC[C
B('3C 61 74'); r8('left');  B('3C 44 74'); r8('left')   # a / ESC[D
B('EB'); r8('next_key')
L('up');    B('31D2 B8 FFFFFFFF EB'); r8('try_dir')
L('down');  B('31D2 B8 01000000 EB'); r8('try_dir')
L('right'); B('BA 01000000 31C0 EB'); r8('try_dir')
L('left');  B('BA FFFFFFFF 31C0')
L('try_dir')                                 # reject 180-degree turns
B('89D7 03 7B 08 75'); r8('accept')
B('89C7 03 7B 0C 74'); r8('next_key')
L('accept')
B('89 53 10 89 43 14')                       # ndx = edx; ndy = eax
L('next_key')
B('FFC9 0F85'); r32('key_loop')
B('E9'); r32('read_more')

L('input_done')
B('8B 43 10 89 43 08 8B 43 14 89 43 0C')     # dx,dy = ndx,ndy
B('8B 43 00 03 43 08')                       # eax = hx + dx
B('8B 53 04 03 53 0C')                       # edx = hy + dy
B('83F8 1E 0F83'); r32('dead')               # x >= 30 (unsigned) -> wall
B('83FA 0E 0F83'); r32('dead')               # y >= 14 -> wall
B('89 43 00 89 53 04')                       # store hx, hy
B('6B D2 1E 01C2 89 53 48')                  # edx = y*30+x; head idx
B('31ED 3B 53 1C 75'); r8('do_dec')          # ate = 0; head == food?
B('FFC5 FF 43 18 FF 43 24 EB'); r8('check')  # ate=1; len++; score++
L('do_dec')                                  # age every body cell
B('8D B3 00010000 B9 A4010000')
L('dec_loop')
B('66 83 3E 00 74 03 66 FF 0E')              # if word[rsi]: dec word[rsi]
B('83C6 02 FFC9 75'); r8('dec_loop')
L('check')
B('66 83 BC 53 00010000 00 0F85'); r32('dead')  # grid[head] != 0 -> bit self
B('8B 43 18 66 89 84 53 00010000')           # grid[head] = len
B('85ED 74'); r8('render')
B('E8'); r32('place_food')

L('render')
B('8D BB 00050000')                          # edi = outbuf
B('BE'); a32('s_hdr1'); B('B9'); a32('n_hdr1'); B('F3A4')
B('8B 43 24 B9 0A000000')                    # eax = score; ecx = 10
B('31D2 F7F1 80C2 30 88 57 02')              # three decimal digits
B('31D2 F7F1 80C2 30 88 57 01')
B('31D2 F7F1 80C2 30 88 57 00')
B('83C7 03')
B('BE'); a32('s_hdr2'); B('B9'); a32('n_hdr2'); B('F3A4')
B('BE'); a32('s_border'); B('B9 21000000 F3A4')
B('31F6 BD 0E000000')                        # cell = 0; rows = 14
L('row')
B('C6 07 23 FFC7 B9 1E000000')               # '#'; cols = 30
L('col')
B('B0 20')                                   # ' '
B('0FB7 94 73 00010000 85D2 74 02 B0 6F')    # body -> 'o'
B('3B 73 1C 75 02 B0 2A')                    # food -> '*'
B('3B 73 48 75 02 B0 40')                    # head -> '@'
B('88 07 FFC7 FFC6 FFC9 75'); r8('col')
B('66 C7 07 230A 83C7 02 FFCD 75'); r8('row')  # "#\n"
B('BE'); a32('s_border'); B('B9 21000000 F3A4')
B('8D B3 00050000 89FA 29F2')                # edx = len
B('BF 01000000 B8 01000000 0F05')            # write(1, outbuf, len)
B('E9'); r32('main_loop')

L('dead')
sys_write('s_over', 13)
L('quit')
B('B8 10000000 31FF BE 02540000 8D 93 80000000 0F05')   # restore termios
sys_write('s_show', 6)
B('B8 3C000000 31FF 0F05')                   # exit(0)

L('place_food')                              # xorshift32 until free cell
B('8B 43 20')
B('89C1 C1E1 0D 31C8')
B('89C1 C1E9 11 31C8')
B('89C1 C1E1 05 31C8')
B('89 43 20 31D2 B9 A4010000 F7F1')
B('66 83 BC 53 00010000 00 75'); r8('place_food')
B('3B 53 48 74'); r8('place_food')
B('89 53 1C C3')

# ---------------- strings ----------------
hdr1 = b'\x1b[H SNAKE    score '
hdr2 = b'\n WASD / arrows    Q quit\n\n'
L('s_init');   prog.append(b'\x1b[?25l\x1b[2J')
L('s_hdr1');   prog.append(hdr1)
L('s_hdr2');   prog.append(hdr2)
L('s_border'); prog.append(b'#' * 32 + b'\n')
L('s_over');   prog.append(b'\n GAME OVER!\n')
L('s_show');   prog.append(b'\x1b[?25h')

# ---------------- link ----------------
HDR = 64 + 56
consts = {'n_hdr1': len(hdr1), 'n_hdr2': len(hdr2)}
size = {'r8': 1, 'r32': 4, 'a32': 4}
labels, pc = {}, BASE + HDR
for it in prog:
    if isinstance(it, bytes): pc += len(it)
    elif it[0] == 'L': labels[it[1]] = pc
    else: pc += size[it[0]]
code, pc = bytearray(), BASE + HDR
for it in prog:
    if isinstance(it, bytes): code += it; pc += len(it); continue
    k, n = it
    if k == 'L': continue
    pc += size[k]
    if k == 'a32': code += struct.pack('<I', labels.get(n, consts.get(n)))
    else:
        d = labels[n] - pc
        if k == 'r8':
            assert -128 <= d <= 127, f'rel8 to {n} out of range: {d}'
            code += struct.pack('<b', d)
        else: code += struct.pack('<i', d)

filesz = HDR + len(code)
elf = (b'\x7fELF\x02\x01\x01' + bytes(9) +
       struct.pack('<HHIQQQIHHHHHH', 2, 0x3E, 1, BASE + HDR, 64, 0, 0, 64, 56, 1, 0, 0, 0) +
       struct.pack('<IIQQQQQQ', 1, 7, 0, BASE, BASE, filesz, 0x2000, 0x1000))
out = elf + code
open('snake', 'wb').write(out)
open('snake.hex', 'w').write(out.hex())
print(f'wrote snake: {len(out)} bytes')
