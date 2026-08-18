% Generate MATLAB golden CSVs from the original HRAP .m sources.
% Run from MATLAB:
%   cd <repo>/scripts
%   make_matlab_golden
%
% Or:
%   matlab -batch "cd('<repo>/scripts'); make_matlab_golden"

function make_matlab_golden(debugFirst)
  if nargin < 1
    debugFirst = false;
  end
  here = fileparts(mfilename('fullpath'));
  root = fileparts(here);
  addpath(fullfile(root, 'HRAP - Matlab', 'core'));
  addpath(fullfile(root, 'HRAP - Matlab', 'util'));

  outdir = fullfile(root, 'tests', 'golden');
  if ~exist(outdir, 'dir')
    mkdir(outdir);
  end

  write_nox(outdir);
  write_interp(root, outdir);

  run_one(root, outdir, 'example_98mm', 'ABS', false, false);
  run_one(root, outdir, 'example_98mm', 'ABS', true, false);
  run_one(root, outdir, 'Rattworks_K240', 'HDPE', false, debugFirst);
  fprintf('MATLAB goldens written to %s\n', outdir);
end

function write_nox(outdir)
  T = (183:1:309)';
  Pv = zeros(size(T)); rho_l = Pv; rho_v = Pv; Hv = Pv; Cp = Pv; Z = Pv;
  for i = 1:numel(T)
    op = NOX(T(i));
    Pv(i) = op.Pv; rho_l(i) = op.rho_l; rho_v(i) = op.rho_v;
    Hv(i) = op.Hv; Cp(i) = op.Cp; Z(i) = op.Z;
  end
  M = [T Pv rho_l rho_v Hv Cp Z];
  write_csv(fullfile(outdir, 'nox_matlab.csv'), 'T,Pv,rho_l,rho_v,Hv,Cp,Z', M);
end

function write_interp(root, outdir)
  pfile = first_existing({ ...
    fullfile(root, 'data', 'propellants', 'mat', 'ABS.mat'), ...
    fullfile(root, 'HRAP - Matlab', 'propellant_configs', 'ABS.mat')});
  S = load(pfile);
  p = S.s;
  OF = [p.prop_OF(1), mean(p.prop_OF), p.prop_OF(end), 0, 99];
  Pc = [p.prop_Pc(1), mean(p.prop_Pc), p.prop_Pc(end), 0, 1e8];
  rows = [];
  for i = 1:numel(OF)
    for j = 1:numel(Pc)
      zi = interp2x(p.prop_OF, p.prop_Pc, p.prop_k, OF(i), Pc(j));
      rows = [rows; OF(i) Pc(j) zi]; %#ok<AGROW>
    end
  end
  write_csv(fullfile(outdir, 'interp2x_matlab.csv'), 'OF,Pc,k', rows);
end

function run_one(root, outdir, motor_name, prop_name, shifting, debugFirst)
  if nargin < 6
    debugFirst = false;
  end
  cfg_path = first_existing({ ...
    fullfile(root, 'data', 'motors', 'mat', [motor_name '.mat']), ...
    fullfile(root, 'HRAP - Matlab', 'motor_configs', [motor_name '.mat'])});
  pfile = first_existing({ ...
    fullfile(root, 'data', 'propellants', 'mat', [prop_name '.mat']), ...
    fullfile(root, 'HRAP - Matlab', 'propellant_configs', [prop_name '.mat'])});
  C = load(cfg_path);
  cfg = C.cfg;
  P = load(pfile);
  prop = P.s;

  [s, x, o] = build_and_run(cfg, prop, shifting, debugFirst);
  if debugFirst
    return
  end
  tag = motor_name;
  if shifting
    tag = [motor_name '_shift'];
  end
  path = fullfile(outdir, [tag '_matlab.csv']);
  write_trace(path, o);
  fprintf('  wrote %s  n=%d  end=%s\n', path, numel(o.t), o.sim_end_cond);
end

function [s, x, o] = build_and_run(cfg, prop, shifting, debugFirst)
  if nargin < 4
    debugFirst = false;
  end
  s = struct();
  s.prop_OF = prop.prop_OF;
  s.prop_Pc = prop.prop_Pc;
  s.prop_k = prop.prop_k;
  s.prop_M = prop.prop_M;
  s.prop_T = prop.prop_T;
  s.prop_Rho = cfg.prop_rho * dens_u(cfg.prop_rho_unit);
  s.prop_nm = char(string(cfg.prop_nm));
  s.mtr_nm = char(string(cfg.mtr_nm));
  s.dt = cfg.dt;
  s.tmax = cfg.t_max;
  s.tburn = cfg.t_burn;
  s.Pa = cfg.Pa * pres_u(cfg.Pa_unit);
  s.grn_OD = cfg.grn_OD * len_u(cfg.grn_OD_unit);
  s.grn_ID = cfg.grn_ID * len_u(cfg.grn_ID_unit);
  s.grn_L = cfg.grn_L * len_u(cfg.grn_L_unit);
  s.cstar_eff = cfg.cstar_eff / 100;
  s.const_OF = cfg.const_OF;
  if isfield(cfg, 'tnk_V_state') && cfg.tnk_V_state
    s.tnk_D = cfg.tnk_D * len_u(cfg.tnk_D_unit);
    s.tnk_V = cfg.tnk_L * len_u(cfg.tnk_L_unit) * 0.25 * pi * s.tnk_D^2;
  else
    s.tnk_V = cfg.tnk_V * vol_u(cfg.tnk_V_unit);
    if cfg.mp_state
      s.tnk_D = cfg.tnk_D * len_u(cfg.tnk_D_unit);
    else
      s.tnk_D = 0;
    end
  end
  if isfield(cfg, 'cmbr_V_state') && cfg.cmbr_V_state
    s.cmbr_V = s.grn_L * 0.25 * pi * s.grn_OD^2;
  else
    s.cmbr_V = cfg.cmbr_V * vol_u(cfg.cmbr_V_unit);
  end
  if shifting
    s.regression_model = @(ss,xx) shift_OF(ss,xx);
    s.prop_Reg = [0.198, 0.325, 0.0];
  else
    s.regression_model = @(ss,xx) const_OF(ss,xx);
    if isfield(prop, 'prop_Reg')
      s.prop_Reg = prop.prop_Reg;
    else
      s.prop_Reg = [0 0 0];
    end
  end
  s.noz_Cd = cfg.noz_Cd;
  s.noz_thrt = cfg.noz_thrt * len_u(cfg.noz_thrt_unit);
  if strcmp(char(string(cfg.noz_def)), 'Nozzle Exit Diameter')
    s.noz_ER = (cfg.noz_ex * len_u(cfg.noz_ex_unit))^2 / s.noz_thrt^2;
  else
    s.noz_ER = cfg.noz_ex;
  end
  s.noz_eff = cfg.noz_eff / 100;
  s.inj_CdA = 0.25 * pi * (cfg.inj_D * len_u(cfg.inj_D_unit))^2 * cfg.inj_Cd;
  s.inj_N = cfg.inj_N;
  vnt = char(string(cfg.vnt_state));
  if strcmp(vnt, 'None')
    s.vnt_S = 0; s.vnt_CdA = 0;
  elseif strcmp(vnt, 'External')
    s.vnt_S = 1; s.vnt_CdA = 0.25 * pi * (cfg.vnt_D * len_u(cfg.vnt_D_unit))^2 * cfg.vnt_Cd;
  else
    s.vnt_S = 2; s.vnt_CdA = 0.25 * pi * (cfg.vnt_D * len_u(cfg.vnt_D_unit))^2 * cfg.vnt_Cd;
  end
  if cfg.mp_state
    s.mp_calc = 1;
    s.mtr_m = cfg.mtr_m * mass_u(cfg.mtr_m_unit);
    s.mtr_cg = cfg.mtr_cg * len_u(cfg.mtr_cg_unit);
    s.tnk_X = cfg.tnk_X * len_u(cfg.tnk_X_unit);
    s.cmbr_X = cfg.cmbr_X * len_u(cfg.cmbr_X_unit);
  else
    s.mp_calc = 0;
    s.mtr_m = 0; s.mtr_cg = 0; s.tnk_X = 0; s.cmbr_X = 0;
  end

  x = struct();
  tnk_dd = char(string(cfg.tnk_dd));
  if strcmp(tnk_dd, 'Starting Tank Pressure')
    Pv = @(T) 7251000*exp((1/(T/309.57))*(-6.71893*(1-T/309.57) + 1.35966*(1-(T/309.57))^(3/2) + -1.3779*(1-(T/309.57))^(5/2) + -4.051*(1-(T/309.57))^5)) - cfg.tnk_cond*pres_u(cfg.T_tnk_unit);
    x.T_tnk = fzero(Pv, 273.15);
  else
    x.T_tnk = temp_u(cfg.tnk_cond, cfg.T_tnk_unit);
  end
  x.ox_props = NOX(x.T_tnk);
  fill_dd = char(string(cfg.fill_dd));
  if strcmp(fill_dd, 'Tank Fill Percentage')
    x.m_o = (cfg.fill/100)*s.tnk_V*x.ox_props.rho_l + (1-cfg.fill/100)*s.tnk_V*x.ox_props.rho_v;
  else
    x.m_o = cfg.fill * mass_u(cfg.fill_unit);
  end
  x.P_tnk = x.ox_props.Pv;
  x.P_cmbr = cfg.P_cmbr * pres_u(cfg.P_cmbr_unit);
  x.mdot_o = 0;
  x.mLiq_new = (s.tnk_V - (x.m_o/x.ox_props.rho_v))/((1/x.ox_props.rho_l)-(1/x.ox_props.rho_v));
  x.mLiq_old = x.mLiq_new + 1;
  x.m_f = 0.25*pi*(s.grn_OD^2 - s.grn_ID^2)*s.prop_Rho*s.grn_L;
  x.m_g = 1.225*(s.cmbr_V - 0.25*pi*(s.grn_OD^2 - s.grn_ID^2)*s.grn_L);
  if shifting
    x.OF = 0;
  else
    x.OF = s.const_OF;
  end
  x.mdot_f = 0; x.mdot_n = 0; x.rdot = 0; x.grn_ID = s.grn_ID; x.dP = 0; x.F_thr = 0;

  n = s.tmax/s.dt + 1;
  o = struct();
  fields = {'t','m_o','P_tnk','P_cmbr','mdot_o','mdot_f','OF','grn_ID','mdot_n','rdot','m_f','F_thr','dP'};
  for k = 1:numel(fields)
    o.(fields{k}) = zeros(1, n);
  end
  o.m_o(1) = x.m_o; o.P_tnk(1) = x.P_tnk; o.P_cmbr(1) = x.P_cmbr;
  o.mdot_o(1) = x.mdot_o; o.mdot_f(1) = x.mdot_f; o.OF(1) = x.OF;
  o.grn_ID(1) = x.grn_ID; o.mdot_n(1) = x.mdot_n; o.rdot(1) = x.rdot; o.m_f(1) = x.m_f;
  if s.mp_calc == 1
    o.m_t = zeros(1, n); o.cg = zeros(1, n);
    mp = mass(s, x);
    o.m_t(1) = mp(1); o.cg(1) = mp(2);
  end
  t = 0;
  if debugFirst
    fprintf('init m_g=%.16g T=%.16g P_tnk=%.16g P_cmbr=%.16g m_o=%.16g m_f=%.16g mLiq=%.16g\n', ...
      x.m_g, x.T_tnk, x.P_tnk, x.P_cmbr, x.m_o, x.m_f, x.mLiq_new);
    fprintf('s cstar_eff=%.16g noz_eff=%.16g ER=%.16g thrt=%.16g cmbr_V=%.16g tnk_V=%.16g inj_CdA=%.16g vnt_CdA=%.16g\n', ...
      s.cstar_eff, s.noz_eff, s.noz_ER, s.noz_thrt, s.cmbr_V, s.tnk_V, s.inj_CdA, s.vnt_CdA);
    [s, x, o, t] = sim_iteration(s, x, o, 0, 2);
    fprintf('after1 k=%.16g M=%.16g T=%.16g cstar=%.16g R=%.16g\n', x.k, x.M, x.T, x.cstar, x.R);
    fprintf('after1 P=%.16g F=%.16g mdot_n=%.16g mdot_o=%.16g mdot_f=%.16g m_g=%.16g rdot=%.16g\n', ...
      x.P_cmbr, x.F_thr, x.mdot_n, x.mdot_o, x.mdot_f, x.m_g, x.rdot);
    return
  end
  [s, x, o, t] = sim_loop(s, x, o, t); %#ok<ASGLU>
end

function write_trace(path, o)
  M = [o.t(:) o.F_thr(:) o.P_tnk(:) o.P_cmbr(:) o.mdot_o(:) o.mdot_f(:) o.OF(:) o.grn_ID(:) o.m_o(:) o.m_f(:)];
  write_csv(path, 't,F_thr,P_tnk,P_cmbr,mdot_o,mdot_f,OF,grn_ID,m_o,m_f', M);
end

function write_csv(path, header, M)
  fid = fopen(path, 'w');
  fprintf(fid, '%s\n', header);
  for i = 1:size(M, 1)
    for j = 1:size(M, 2)
      if j > 1
        fprintf(fid, ',');
      end
      fprintf(fid, '%.16g', M(i, j));
    end
    fprintf(fid, '\n');
  end
  fclose(fid);
end

function p = first_existing(cands)
  p = '';
  for i = 1:numel(cands)
    if exist(cands{i}, 'file')
      p = cands{i};
      return
    end
  end
  error('missing asset, tried: %s', strjoin(cands, ', '));
end

function u = len_u(name)
  name = char(string(name));
  switch name
    case 'mm', u = 0.001;
    case 'cm', u = 0.01;
    case 'm', u = 1;
    case 'in', u = 0.0254;
    case 'ft', u = 0.3048;
    otherwise, u = 1;
  end
end

function u = vol_u(name)
  name = char(string(name));
  switch name
    case {'cm^3','cc'}, u = 0.01^3;
    case 'L', u = 0.001;
    case 'in^3', u = 0.0254^3;
    case 'ft^3', u = 0.3048^3;
    case 'Gal', u = 0.00378541;
    case 'm^3', u = 1;
    otherwise, u = 1;
  end
end

function u = pres_u(name)
  name = char(string(name));
  switch name
    case 'psi', u = 101325/14.696;
    case 'psf', u = 101325/14.696*144;
    case 'atm', u = 101325;
    case 'MPa', u = 1e6;
    case 'kPa', u = 1000;
    case {'Bar','bar'}, u = 1e5;
    case 'Pa', u = 1;
    otherwise, u = 1;
  end
end

function u = mass_u(name)
  name = char(string(name));
  switch name
    case 'lbm', u = 0.453592;
    case 'oz', u = 0.0283495;
    case 'g', u = 0.001;
    case 'kg', u = 1;
    otherwise, u = 1;
  end
end

function u = dens_u(name)
  name = char(string(name));
  switch name
    case 'lb/in^3', u = 1/(2.205*0.0254^3);
    case 'lb/ft^3', u = 1/(2.205*0.3048^3);
    case 'g/cm^3', u = 1000;
    case 'kg/m^3', u = 1;
    otherwise, u = 1;
  end
end

function T = temp_u(val, name)
  name = char(string(name));
  switch name
    case 'C', T = val + 273.15;
    case 'R', T = val / 1.8;
    case 'F', T = ((val-32)/1.8)+273.15;
    otherwise, T = val;
  end
end
