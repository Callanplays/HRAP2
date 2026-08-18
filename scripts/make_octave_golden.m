% Octave-friendly wrapper. The core .m files need no toolboxes.
%   octave --eval "cd('scripts'); make_octave_golden"
function make_octave_golden()
  make_matlab_golden();
end
