from nmigen import *
from nmigen.sim import *
from nmigen_boards.upduino_v2 import *
from nmigen_soc.wishbone import *
from nmigen_soc.memory import *

from spi_rom import *

import sys

# Dummy LED class for testing.
class DummyLED():
  def __init__( self, name ):
    self.o = Signal( 1, reset = 0b0, name = '%s_o'%name )

# Basic instruction definitions.
# Red LED on/off
RED_ON  = 0x00000009
RED_OFF = 0x00000001
# Green LED on/off
GRN_ON  = 0x0000000A
GRN_OFF = 0x00000002
# Blue LED on/off
BLU_ON  = 0x0000000B
BLU_OFF = 0x00000003
# Delay for 'xxxxxxx' cycles.
def DELAY( cycles ):
  return ( ( 0x4 | ( cycles << 4 ) ) & 0xFFFFFFFF )
# Jump back to word 0.
RETURN  = 0x00000000

class Memory_Test( Elaboratable ):
  def __init__( self, memory ):
    # Simulated memory module.
    self.mem = memory
    # Current memory pointer.
    self.pc = Signal( self.mem.addr_width, reset = 0 )
    # Delay counter.
    self.dc = Signal( 28, reset = 0 )

  def elaborate( self, platform ):
    m = Module()
    m.submodules.mem = self.mem

    # LED resources.
    if platform is None:
      rled = DummyLED( 'led_r' )
      gled = DummyLED( 'led_g' )
      bled = DummyLED( 'led_b' )
    else:
      rled = platform.request( 'led_r', 0 )
      gled = platform.request( 'led_g', 0 )
      bled = platform.request( 'led_b', 0 )

    # Set bus address to the 'program counter' value.
    m.d.comb += self.mem.adr.eq( self.pc )

    # State machine:
    # * 'FETCH':   Retrieve the next instruction from memory.
    # * 'PROCESS': Execute the current instruction.
    with m.FSM():
      # 'FETCH' state: Get the next word from memory.
      with m.State( 'FETCH' ):
        # Pulse 'stb' and 'cyc' to start the bus transaction.
        m.d.sync += [
          self.mem.stb.eq( 1 ),
          self.mem.cyc.eq( 1 )
        ]
        # Proceed once 'ack' is asserted.
        with m.If( self.mem.ack == 1 ):
          # Reset the delay counter, and clear 'stb' / 'cyc' to end
          # the bus transaction. This also causes 'ack' to be cleared.
          m.d.sync += [
            self.dc.eq( 0 ),
            self.mem.stb.eq( 0 ),
            self.mem.cyc.eq( 0 )
          ]
          m.next = 'PROCESS'
        # Read is ongoing while 'ack' is not asserted.
        with m.Else():
          m.next = 'FETCH'
      # 'PROCESS' state: execute the retrieved instruction.
      with m.State( 'PROCESS' ):
        # Unless otherwise specified, increment the PC address
        # and proceed back to the 'FETCH' state.
        m.d.sync += self.pc.eq( self.pc + 4 )
        m.next = 'FETCH'
        # If the word is 0 or -1, reset PC address to 0 instead of
        # incrementing it. 0xFFFFFFFF can indicate an error or
        # uninitialized SPI memory, so it's a good 'return' trigger.
        with m.If( ( self.mem.dat_r == 0x00000000 ) |
                   ( self.mem.dat_r == 0xFFFFFFFF ) ):
          m.d.sync += self.pc.eq( 0 )
        # If the 4 LSbits equal 0x4, delay for a number of cycles
        # indicated by the remaining 28 MSbits.
        with m.Elif( self.mem.dat_r[ :4 ] == 4 ):
          # If the delay has not finished, increment 'delay counter'
          # without changing the PC address, and return to the
          # 'PROCESS' state instead of moving on to 'NEXT'.
          with m.If( self.dc != ( self.mem.dat_r >> 4 ) ):
            m.d.sync += [
              self.dc.eq( self.dc + 1 ),
              self.pc.eq( self.pc )
            ]
            m.next = 'PROCESS'
        # If the 3 LSbits == 3, set the blue LED to the 4th bit.
        with m.Elif( self.mem.dat_r[ :3 ] == 3 ):
          m.d.sync += bled.o.eq( self.mem.dat_r[ 3 ] )
        # If the 3 LSbits == 2, set the green LED to the 4th bit.
        with m.Elif( self.mem.dat_r[ :3 ] == 2 ):
          m.d.sync += gled.o.eq( self.mem.dat_r[ 3 ] )
        # If the 3 LSbits == 1, set the red LED to the 4th bit.
        with m.Elif( self.mem.dat_r[ :3 ] == 1 ):
          m.d.sync += rled.o.eq( self.mem.dat_r[ 3 ] )

    # (End of memory and finite state machine test logic.)
    return m

# Test program to run.
test_prog = [
  BLU_ON, DELAY( 5000000 ), GRN_ON, DELAY( 5000000 ),
  BLU_OFF, RED_ON, DELAY( 5000000 ), RED_OFF,
  DELAY( 10000000 ), GRN_OFF, DELAY( 5000000 ), RETURN
]
# 'main' method to simulate or build the test.
if __name__ == "__main__":
  # If the file was run with '-b', build for an iCE40UP5K breakout board
  if ( len( sys.argv ) == 2 ) and ( sys.argv[ 1 ] == '-b' ):
    offset = 2 * 1024 * 1024
    dut = Memory_Test( SPI_ROM( offset, offset + 1024, None ) )
    UpduinoV2Platform().build( dut )
  # If the file was run with '-w', write a binary file to write
  # to SPI Flash memory. (`iceprog -o 2M prog.bin`)
  elif ( len( sys.argv ) == 2 ) and ( sys.argv[ 1 ] == '-w' ):
    with open( 'prog.bin', 'wb' ) as f:
      for i in test_prog:
        f.write( bytes( [ ( i >> 0  ) & 0xFF,
                          ( i >> 8  ) & 0xFF,
                          ( i >> 16 ) & 0xFF,
                          ( i >> 24 ) & 0xFF ] ) )
  # If no arguments were passed in, simulate the design.
  else:
    offset = 2 * 1024 * 1024
    dut = Memory_Test( SPI_ROM( offset, offset + 1024, [
      BLU_ON, DELAY( 5 ), GRN_ON, DELAY( 5 ), BLU_OFF, RED_ON,
      DELAY( 10 ), RED_OFF, DELAY( 5 ), GRN_OFF, DELAY( 5 ), RETURN
    ] ) )
    sim = Simulator(dut)
    with sim.write_vcd('test.vcd'):
      # Simulate running for 5000 clock cycles.
      def proc():
        for i in range( 5000 ):
          yield Tick()
          yield Settle()
      sim.add_clock( 1e-6 )
      sim.add_sync_process( proc )
      sim.run()
