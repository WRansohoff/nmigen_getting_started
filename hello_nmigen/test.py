from nmigen import *

class TestModule( Elaboratable ):
  def __init__( self ):
    self.count = Signal( 16, reset = 0 )
    self.ncount = Signal( 16, reset = 0 )

  def elaborate( self, platform ):
    m = Module()
    m.d.comb += self.ncount.eq( ~self.count )
    m.d.sync += self.count.eq( self.count + 1 )
    with m.If( self.count == 42 ):
      m.d.sync += self.count.eq( 0 )
    return m

from nmigen.sim import *

if __name__ == "__main__":
  dut = TestModule()
  sim = Simulator(dut)
  with sim.write_vcd('test.vcd'):
    def proc():
      # Run for 50 clock cycles, and check that the 'count' signal
      # equals the number of elapsed cycles. This should start
      # to fail after tick #42, because the 'count' value resets.
      for i in range( 50 ):
        c = yield dut.count
        if c == i:
          print( "PASS: count == %d"%i )
        else:
          print( "FAIL: count != %d (got: %d)"%( i, c ) )
        yield Tick()
    sim.add_clock( 1e-6 )
    sim.add_sync_process( proc )
    sim.run()
