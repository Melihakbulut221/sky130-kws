# Reserve margin for extracted interconnect and buffer trees during placement.
# base.sdc handles set_propagated_clock and unset_propagated_clock per stage.
if {$::env(STEP_ID) ne "OpenROAD.STAPostPNR"} {
    set ::env(MAX_TRANSITION_CONSTRAINT) 0.50
    set ::env(MAX_FANOUT_CONSTRAINT) 8
    set ::env(MAX_CAPACITANCE_CONSTRAINT) 0.14
}
source $::env(SCRIPTS_DIR)/base.sdc
