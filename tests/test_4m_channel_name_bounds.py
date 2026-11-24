#!/usr/bin/env python3
"""Actual 4M renderer must not let long channel names overwrite M19/M24."""
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
text=(ROOT/'ui/helper.c').read_text()
a=text.index('void UI_PrintStringSmall(')
b=text.index('\nvoid UI_PrintStringSmallDoubleHeight',a)
function=text[a:b]
font=(ROOT/'artifacts/4m/messaging/zh/eeprom-assets/ascii-fonts.bin').read_bytes()
small=font[220+288:]
prelude=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define LCD_WIDTH 128
#define FRAME_LINES 7
static uint8_t gFrameBuffer[FRAME_LINES][LCD_WIDTH];
static bool show_move_flag;
static uint8_t is_chn(uint8_t c) { return c>=128?1:255; }
static void set_bit(uint8_t *p, unsigned bit) { *p |= 1u<<bit; }
static void EEPROM_ReadBuffer(unsigned address, void *p, unsigned count) {
 if(address>=0x267C && address+count<=0x28B0) {
  memcpy(p,SMALL + address-0x267C,count);
 } else {
  assert(address>=0x2E00 && address+count<=0x1E1E6);
  memset(p,0x55,count);
 }
}
'''.replace('SMALL','small_font')
body=r'''
static void check(const char *number, const char *name, unsigned start, unsigned line) {
 memset(gFrameBuffer,0xA5,sizeof(gFrameBuffer));
 show_move_flag=false;
 UI_PrintStringSmall(number,2,0,line+1);
 uint8_t before[sizeof(gFrameBuffer)];memcpy(before,gFrameBuffer,sizeof(before));
 show_move_flag=true;
 UI_PrintStringSmall(name,start,0,line);
 unsigned row=line+start/LCD_WIDTH, col=start%LCD_WIDTH;
 // The name may only draw to the right of Start on its two display pages.
 for(unsigned r=0;r<FRAME_LINES;r++) for(unsigned c=0;c<LCD_WIDTH;c++)
  if((r!=row && r!=row+1) || c<col)
   assert(gFrameBuffer[r][c]==before[r*LCD_WIDTH+c]);
 show_move_flag=false;
}
int main(void) {
 const char *names[]={"ABCDEFGHIJKLMNOP", "ABCDEFGHIJKLM", "ABCDEFGHIJKLMN", "ABC",
  "\xB0\xA1\xB0\xA2\xB0\xA3\xB0\xA4\xB0\xA5\xB0\xA6\xB0\xA7\xB0\xA8",
  "ABCDEFGH\xB0\xA1\xB0\xA2\xB0\xA3\xB0\xA4"};
 const char *numbers[]={"M19","M24","M19.","M24."};
 for(unsigned i=0;i<sizeof(numbers)/sizeof(*numbers);i++)
  for(unsigned j=0;j<sizeof(names)/sizeof(*names);j++)
   for(unsigned line=0;line<=3;line+=3) {
    check(numbers[i],names[j],32,line);
    check(numbers[i],names[j],36,line);
   }
 // Existing callers use Start >= 128 to address the following display page.
 check("M19","ABCDEFGHIJKLM",128+24,0);
 puts("M19/M24 labels preserved for 13-16 ASCII, Chinese/mixed names and both VFOs");
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp); src=p/'render.c'
 src.write_text('#define ENABLE_CHINESE_FULL 4\n#define CHN_FONT_HIGH 12\n#define CHN_FONT_WIDTH 11\n#define IS_BIT_SET(x,b) ((x)&(1u<<(b)))\nstatic const unsigned char small_font[]={' + ','.join(str(b) for b in small)+'};\n'+prelude+function+body)
 subprocess.run(['cc','-std=c99','-funsigned-char','-fsanitize=undefined,bounds','-fno-sanitize-recover=all',str(src),'-o',str(p/'render')],check=True)
 subprocess.run([str(p/'render')],check=True)
