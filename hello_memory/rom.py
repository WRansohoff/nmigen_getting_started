from nmigen import *
from math import ceil, log2
from nmigen.sim import *
from nmigen_soc.memory import *
from nmigen_soc.wishbone import *

# Simulated read-only memory module.
class ROM( Elaboratable, Interface ):
  def __init__( self, data ):
    # Record size.
    self.size = len( data )
    # Data storage.
    self.data = Memory( width = 32, depth = self.size, init = data )
    # Memory read port.
    self.r = self.data.read_port()

    # Initialize Wishbone bus interface.
    Interface.__init__( self,
                        data_width = 32,
                        addr_width = ceil( log2( self.size + 1 ) ) )
    self.memory_map = MemoryMap( data_width = self.data_width,
                                 addr_width = self.addr_width,
                                 alignment = 0 )

  def elaborate( self, platform ):
    m = Module()
    # Register the read port submodule.
    m.submodules.r = self.r

    # 'ack' signal should rest 0.
    m.d.sync += self.ack.eq( 0 )
    # Simulated reads only take one cycle, but only acknowledge
    # them after 'cyc' and 'stb' are asserted.
    with m.If( self.cyc ):
      m.d.sync += self.ack.eq( self.stb )

    # Set 'dat_r' bus signal to the value in the
    # requested 'data' array index.
    m.d.comb += [
      self.r.addr.eq( self.adr ),
      self.dat_r.eq( self.r.data )
    ]

    # End of simulated memory module.
    return m

# Testbench:
# Perform an individual 'memory read' unit test.
def rom_read_ut( rom, address, expected ):
  # Set address, and wait a tick.
  yield rom.adr.eq( address )
  yield Tick()
  # Done. Check the result after combinatorial logic settles.
  yield Settle()
  actual = yield rom.dat_r
  if expected == actual:
    print( "PASS: Memory[ 0x%04X ] = 0x%08X"%( address, expected ) )
  else:
    print( "FAIL: Memory[ 0x%04X ] = 0x%08X (got: 0x%08X)"
           %( address, expected, actual ) )

# Run a basic series of tests when this file is run.
if __name__ == "__main__":
  # Create a test memory with 20 bytes of data.
  dut = ROM( [ 0x01234567, 0x89ABCDEF,
               0x0C0FFEE0, 0xDEC0FFEE,
               0xFEEBEEDE ] )
  # Run the simulation.
  sim = Simulator(dut)
  with sim.write_vcd('rom.vcd'):
    def proc():
      # Test reads.
      yield from rom_read_ut( dut, 0, 0x01234567 )
      yield from rom_read_ut( dut, 1, 0x89ABCDEF )
      yield from rom_read_ut( dut, 2, 0x0C0FFEE0 )
      yield from rom_read_ut( dut, 3, 0xDEC0FFEE )
      yield from rom_read_ut( dut, 4, 0xFEEBEEDE )
    sim.add_clock( 1e-6 )
    sim.add_sync_process( proc )
    sim.run()
