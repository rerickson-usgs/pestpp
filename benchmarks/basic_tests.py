import os
import sys
import shutil
import platform
import numpy as np
import pandas as pd
import platform
import pyemu

bin_path = os.path.join("test_bin")
if "linux" in platform.platform().lower():
    bin_path = os.path.join(bin_path,"linux")
elif "darwin" in platform.platform().lower():
    bin_path = os.path.join(bin_path,"mac")
else:
    bin_path = os.path.join(bin_path,"win")

bin_path = os.path.abspath("test_bin")
os.environ["PATH"] += os.pathsep + bin_path


bin_path = os.path.join("..","..","..","bin")


use_intel= os.getenv('USE_INTEL', False)
# if len(sys.argv) > 1 and sys.argv[1].lower() == 'intel':
#     use_intel = True
#     print("using intel windows binaries")


if "windows" in platform.platform().lower():
    if use_intel:
        print("using intel windows binaries")
        exe_path = os.path.join(bin_path, "iwin", "ipestpp-ies.exe")
    else:
        exe_path = os.path.join(bin_path, "win", "pestpp-ies.exe")
elif "darwin" in platform.platform().lower():
    exe_path = os.path.join(bin_path,  "mac", "pestpp-ies")
else:
    exe_path = os.path.join(bin_path, "linux", "pestpp-ies")


noptmax = 4
num_reals = 20
port = 4020

def basic_test(model_d="ies_10par_xsec"):
    pyemu.Ensemble.reseed()
    base_d = os.path.join(model_d, "template")
    new_d = os.path.join(model_d, "test_template")
    if os.path.exists(new_d):
        shutil.rmtree(new_d)
    shutil.copytree(base_d, new_d)
    print(platform.platform().lower())
    local=True
    if "linux" in platform.platform().lower() and "10par" in model_d:
        #print("travis_prep")
        #prep_for_travis(model_d)
        local=False
    pst = pyemu.Pst(os.path.join(new_d, "pest.pst"))
    print(pst.model_command)
    
    # set first par as fixed
    #pst.parameter_data.loc[pst.par_names[0], "partrans"] = "fixed"

    pst.observation_data.loc[pst.nnz_obs_names,"weight"] = 1.0

    # set noptmax
    pst.control_data.noptmax = noptmax

    # wipe all pestpp options
    pst.pestpp_options = {}
    pst.pestpp_options["ies_num_reals"] = num_reals
    pst.pestpp_options["lambda_scale_fac"] = 1.0
    pst.pestpp_options["ies_lambda_mults"] = 1.0
    # write a generic 2D cov
    if os.path.exists(os.path.join(new_d,"prior.jcb")):
        cov = pyemu.Cov.from_binary(os.path.join(new_d,"prior.jcb"))
        #cov.to_ascii(os.path.join(new_d,"prior.cov"))
    elif os.path.exists(os.path.join(new_d, "prior.cov")):
        cov = pyemu.Cov.from_ascii(os.path.join(new_d, "prior.cov"))
    else:
        cov = pyemu.Cov.from_parameter_data(pst)
        cov = pyemu.Cov(cov.as_2d, names=cov.row_names)
        #cov.to_ascii(os.path.join(new_d, "prior.cov"))
        cov.to_binary(os.path.join(new_d, "prior.jcb"))

    # draw some ensembles
    idx = [i for i in range(num_reals)]
    idx[-1] = "base"
    pe = pyemu.ParameterEnsemble.from_gaussian_draw(pst, cov=cov, num_reals=num_reals,
                                                    use_homegrown=True,group_chunks=True)
    pe.index = idx
    pe.to_csv(os.path.join(new_d, "par.csv"))
    pe.to_binary(os.path.join(new_d, "par.jcb"))
    pe.to_csv(os.path.join(new_d, "sweep_in.csv"))
    pe.loc[:, pst.adj_par_names].to_csv(os.path.join(new_d, "par_some.csv"))
    pe.iloc[:-3, :].to_csv(os.path.join(new_d, "restart_failed_par.csv"))
    oe = pyemu.ObservationEnsemble.from_id_gaussian_draw(pst, num_reals=num_reals)
    oe.index = idx
    oe.to_csv(os.path.join(new_d, "obs.csv"))
    oe.iloc[:-3, :].to_csv(os.path.join(new_d, "restart_failed_base_obs.csv"))
    oe.to_binary(os.path.join(new_d, "obs.jcb"))

    pst.control_data.noptmax = 0
    pst.write(os.path.join(new_d, "pest.pst"))
    pyemu.os_utils.run("{0} pest.pst".format(exe_path),cwd=new_d)
    df = pd.read_csv(os.path.join(new_d,"pest.phi.group.csv"))
    assert df.loc[0,"head"] == 0.5,df
    #return
    pst.control_data.noptmax = noptmax
    pst.write(os.path.join(new_d, "pest.pst"))
    

    
    m_d = os.path.join(model_d,"master_pestpp_sen")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    pyemu.os_utils.start_slaves(new_d, exe_path.replace("-ies","-sen"), "pest.pst", 5, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)
    df = pd.read_csv(os.path.join(m_d, "pest.mio"),index_col=0)

    # run sweep
    m_d = os.path.join(model_d,"master_sweep1")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    pyemu.os_utils.start_slaves(new_d, exe_path.replace("-ies","-swp"), "pest.pst", 5, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)
    df = pd.read_csv(os.path.join(m_d, "sweep_out.csv"),index_col=0)
    
    m_d = os.path.join(model_d,"master_pestpp-glm")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    pyemu.os_utils.start_slaves(new_d, exe_path.replace("-ies","-glm"), "pest.pst", 10, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)

    m_d = os.path.join(model_d,"master_pestpp-ies")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    pyemu.os_utils.start_slaves(new_d, exe_path, "pest.pst", 10, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)



def glm_save_binary_test():
    model_d = "ies_10par_xsec"
    local = True
    if "linux" in platform.platform().lower() and "10par" in model_d:
        # print("travis_prep")
        # prep_for_travis(model_d)
        local = False

    t_d = os.path.join(model_d, "template")
    m_d = os.path.join(model_d, "master_save_binary")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    pst = pyemu.Pst(os.path.join(t_d, "pest.pst"))
    pst.pestpp_options = {"num_reals":30,"save_binary":True}
    pst.control_data.noptmax = 1
    pst.write(os.path.join(t_d, "pest_save_binary.pst"))
    pyemu.os_utils.start_slaves(t_d, exe_path.replace("-ies", "-glm"), "pest_save_binary.pst", 10, master_dir=m_d,
                                slave_root=model_d, local=local, port=port)

    pe = pyemu.ParameterEnsemble.from_binary(pst=pst,filename=os.path.join(m_d,"pest_save_binary.post.paren.jcb"))
    pe = pyemu.ObservationEnsemble.from_binary(pst=pst,filename=os.path.join(m_d, "pest_save_binary.post.obsen.jcb"))

def sweep_forgive_test():
    model_d = "ies_10par_xsec"
    local=True
    if "linux" in platform.platform().lower() and "10par" in model_d:
        #print("travis_prep")
        #prep_for_travis(model_d)
        local=False
    
    t_d = os.path.join(model_d,"template")
    m_d = os.path.join(model_d,"master_sweep_forgive")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    pst = pyemu.Pst(os.path.join(t_d,"pest.pst"))
    pe = pyemu.ParameterEnsemble.from_uniform_draw(pst,num_reals=50)#.loc[:,pst.par_names[:2]]
    pe.loc[:,pst.par_names[2:]] = pst.parameter_data.loc[pst.par_names[2:],"parval1"].values
    pe.to_csv(os.path.join(t_d,"sweep_in.csv"))
    pst.pestpp_options["sweep_forgive"] = True
    pst.write(os.path.join(t_d,"pest_forgive.pst"))
    pyemu.os_utils.start_slaves(t_d, exe_path.replace("-ies","-swp"), "pest_forgive.pst", 10, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)
    df1 = pd.read_csv(os.path.join(m_d, "sweep_out.csv"),index_col=0)

    pe = pe.loc[:,pst.par_names[:2]]
    pe.to_csv(os.path.join(t_d,"sweep_in.csv"))
    pst.pestpp_options["sweep_forgive"] = True
    pst.write(os.path.join(t_d,"pest_forgive.pst"))
    pyemu.os_utils.start_slaves(t_d, exe_path.replace("-ies","-swp"), "pest_forgive.pst", 10, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)
    df2 = pd.read_csv(os.path.join(m_d, "sweep_out.csv"),index_col=0)
    diff = df1 - df2
    print(diff.max())
    assert diff.max().max() == 0.0


def inv_regul_test():
    model_d = "ies_10par_xsec"
    local=True
    if "linux" in platform.platform().lower() and "10par" in model_d:
        #print("travis_prep")
        #prep_for_travis(model_d)
        local=False
    
    t_d = os.path.join(model_d,"template")
    m_d = os.path.join(model_d,"master_inv_regul")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    pst = pyemu.Pst(os.path.join(t_d,"pest.pst"))
    #pyemu.helpers.zero_order_tikhonov(pst)
    #pst.control_data.pestmode = "regularization"
    pst.reg_data.phimlim = 2
    pst.reg_data.phimaccept = 2.2
    pst.control_data.noptmax = 10
    pst.write(os.path.join(t_d,"pest_regul.pst"))
    pyemu.os_utils.start_slaves(t_d, exe_path.replace("-ies","-glm"), "pest_regul.pst", 10, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)
    

def tie_by_group_test():
    model_d = "ies_10par_xsec"
    local=True
    if "linux" in platform.platform().lower() and "10par" in model_d:
        #print("travis_prep")
        #prep_for_travis(model_d)
        local=False
    
    t_d = os.path.join(model_d,"template")
    m_d = os.path.join(model_d,"master_tie_by_group")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    pst = pyemu.Pst(os.path.join(t_d,"pest.pst")) 
    par = pst.parameter_data
    tied_names = pst.adj_par_names[:3]
    par.loc[tied_names[1:3],"partrans"] = "tied"
    par.loc[tied_names[1:3],"partied"] = tied_names[0]
    pst.pestpp_options = {}
    pst.pestpp_options["ies_num_reals"] = 10
    pst.pestpp_options["ies_lambda_mults"] = 1.0
    pst.pestpp_options["lambda_scale_fac"] = 1.0
    pst.pestpp_options["tie_by_group"] = True
    pst.control_data.noptmax = 2
    pst.write(os.path.join(t_d,"pest_tied.pst"))
    
    pyemu.os_utils.start_slaves(t_d, exe_path, "pest_tied.pst", 10, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)
    df = pd.read_csv(os.path.join(m_d,"pest_tied.{0}.par.csv".format(pst.control_data.noptmax)),index_col=0)
    df.columns = df.columns.str.lower()
    print(df.loc[:,tied_names].std(axis=1).apply(np.abs).max())
    assert df.loc[:,tied_names].std(axis=1).apply(np.abs).max() < 1.0e-8

    df.to_csv(os.path.join(t_d,"sweep_in.csv"))
    pyemu.os_utils.start_slaves(t_d, exe_path.replace("-ies","-swp"), "pest_tied.pst", 5, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)

    pyemu.os_utils.start_slaves(t_d, exe_path.replace("-ies","-glm"), "pest_tied.pst", 5, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)
    jco = pyemu.Jco.from_binary(os.path.join(m_d,"pest_tied.jcb"))
    assert jco.shape[1] == 2,jco.shape

def unc_file_test():
    model_d = "ies_10par_xsec"
    local=True
    if "linux" in platform.platform().lower() and "10par" in model_d:
        #print("travis_prep")
        #prep_for_travis(model_d)
        local=False
    
    t_d = os.path.join(model_d,"template")
    m_d = os.path.join(model_d,"master_uncfile")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    shutil.copytree(t_d,m_d)
    pst = pyemu.Pst(os.path.join(m_d,"pest.pst"))
    cov = pyemu.Cov.from_parameter_data(pst)
    cov.to_uncfile(os.path.join(m_d,"pest.unc"),covmat_file=os.path.join(m_d,"cov.mat"),var_mult=2.0,include_path=False)
    pst.pestpp_options = {}
    pst.pestpp_options["parcov"] = "pest.unc"
    pst.pestpp_options["ies_num_reals"] = 10000
    pst.pestpp_options["ies_verbose_level"] = 3
    pst.control_data.noptmax = -2
    pst.write(os.path.join(m_d,"pest_unc.pst"))
    pyemu.os_utils.run("{0} {1}".format(exe_path,"pest_unc.pst"),cwd=m_d)

    pe_1 = pd.read_csv(os.path.join(m_d,"pest_unc.0.par.csv"),index_col=0).apply(np.log10)

    cov = pyemu.Cov.from_parameter_data(pst)
    cov *= 2.0
    cov.to_uncfile(os.path.join(m_d,"pest.unc"),covmat_file=os.path.join(m_d,"cov.mat"),var_mult=1.0,include_path=False)
    pst.pestpp_options = {}
    pst.pestpp_options["parcov"] = "cov.mat"
    pst.pestpp_options["ies_num_reals"] = 10000
    pst.pestpp_options["ies_verbose_level"] = 3 
    pst.control_data.noptmax = -2
    pst.write(os.path.join(m_d,"pest_unc.pst"))
    pyemu.os_utils.run("{0} {1}".format(exe_path,"pest_unc.pst"),cwd=m_d)
    pe_2 = pd.read_csv(os.path.join(m_d,"pest_unc.0.par.csv"),index_col=0).apply(np.log10)
    diff = pe_1 - pe_2
    print(pe_1.std(ddof=0)**2)
    print(pe_2.std(ddof=0)**2)
    print(diff.sum())
    assert diff.sum().max() < 1.0e-10

def parchglim_test():
    model_d = "ies_10par_xsec"
    local=True
    if "linux" in platform.platform().lower() and "10par" in model_d:
        #print("travis_prep")
        #prep_for_travis(model_d)
        local=False
    
    t_d = os.path.join(model_d,"template")
    m_d = os.path.join(model_d,"master_parchglim")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    shutil.copytree(t_d,m_d)
    pst = pyemu.Pst(os.path.join(m_d,"pest.pst"))
    fpm = 1.05
    pst.control_data.facparmax = fpm
    par = pst.parameter_data
    par.loc[pst.par_names[1:],"partrans"] = "fixed"
    par.loc[pst.par_names[0],"partrans"] = "log"
    par.loc[pst.par_names[0],"parchglim"] = "factor"
    par.loc[pst.par_names[0],"parval1"] = 1.0
    
    pst.control_data.noptmax = 1
    pst.pestpp_options["lambdas"] = 1.0
    pst.write(os.path.join(m_d,"pest_parchglim.pst"))
    pyemu.os_utils.run("{0} pest_parchglim.pst".format(exe_path.replace("-ies","-glm")),cwd=m_d)
    p_df = pyemu.pst_utils.read_parfile(os.path.join(m_d,"pest_parchglim.par"))
    assert p_df.loc["stage","parval1"] == fpm

    rpm = 0.1
    par.loc[pst.par_names[0],"parchglim"] = "relative"
    pst.control_data.relparmax = rpm
    pst.write(os.path.join(m_d,"pest_parchglim.pst"))
    pyemu.os_utils.run("{0} pest_parchglim.pst".format(exe_path.replace("-ies","-glm")),cwd=m_d)
    p_df = pyemu.pst_utils.read_parfile(os.path.join(m_d,"pest_parchglim.par"))
    print(par)
    print(p_df)
    assert p_df.loc["stage","parval1"] == par.loc["stage","parval1"] + (rpm * par.loc["stage","parval1"])


    par.loc[pst.par_names[0],"partrans"] = "none"
    par.loc[pst.par_names[0],"parlbnd"] = -10.0
    par.loc[pst.par_names[0],"parubnd"] = 0.0   
    par.loc[pst.par_names[0],"parchglim"] = "factor"
    par.loc[pst.par_names[0],"parval1"] = -1.0
    pst.write(os.path.join(m_d,"pest_parchglim.pst"))
    pyemu.os_utils.run("{0} pest_parchglim.pst".format(exe_path.replace("-ies","-glm")),cwd=m_d)
    p_df = pyemu.pst_utils.read_parfile(os.path.join(m_d,"pest_parchglim.par"))
    print(p_df)
    assert p_df.loc["stage","parval1"] == par.loc["stage","parval1"] + np.abs(par.loc["stage","parval1"] * (fpm-1))

    rpm = 1.1
    par.loc[pst.par_names[0],"partrans"] = "none"
    par.loc[pst.par_names[0],"parlbnd"] = -10.0
    par.loc[pst.par_names[0],"parubnd"] = 10.0   
    par.loc[pst.par_names[0],"parchglim"] = "relative"
    par.loc[pst.par_names[0],"parval1"] = -1.0
    pst.control_data.relparmax = rpm
    pst.write(os.path.join(m_d,"pest_parchglim.pst"))
    pyemu.os_utils.run("{0} pest_parchglim.pst".format(exe_path.replace("-ies","-glm")),cwd=m_d)
    p_df = pyemu.pst_utils.read_parfile(os.path.join(m_d,"pest_parchglim.par"))
    print(p_df)
    print(p_df.loc["stage","parval1"],par.loc["stage","parval1"] + rpm)
    assert np.abs(p_df.loc["stage","parval1"] - (par.loc["stage","parval1"] + rpm)) < 1.0e-6


    par.loc[pst.par_names[1:],"partrans"] = "log"
    par.loc[pst.par_names[1:],"parchglim"] = "factor"
    pst.control_data.facparmax = 5.0
    
    pst.write(os.path.join(m_d,"pest_parchglim.pst"))
    pyemu.os_utils.run("{0} pest_parchglim.pst".format(exe_path.replace("-ies","-glm")),cwd=m_d)
    p_df = pyemu.pst_utils.read_parfile(os.path.join(m_d,"pest_parchglim.par"))
    print(p_df)
    print(p_df.loc["stage","parval1"],par.loc["stage","parval1"] + rpm)
    assert np.abs(p_df.loc["stage","parval1"] - (par.loc["stage","parval1"] + rpm)) < 1.0e-6

    # currently something is up with the upgrade calcs in pestpp-glm
    # so this test just makes sure it runs without throwing an exception
    rpm = 1.1
    par.loc[pst.par_names[1:],"partrans"] = "fixed"
    par.loc[pst.par_names[1:],"parchglim"] = "factor"
    par.loc[pst.par_names[0],"partrans"] = "none"
    par.loc[pst.par_names[0],"parlbnd"] = -10.0
    par.loc[pst.par_names[0],"parubnd"] = 10.0   
    par.loc[pst.par_names[0],"parchglim"] = "relative"
    par.loc[pst.par_names[0],"parval1"] = 0.0
    pst.control_data.relparmax = rpm
    pst.write(os.path.join(m_d,"pest_parchglim.pst"))
    pyemu.os_utils.run("{0} pest_parchglim.pst".format(exe_path.replace("-ies","-glm")),cwd=m_d)
    p_df = pyemu.pst_utils.read_parfile(os.path.join(m_d,"pest_parchglim.par"))
    print(p_df)
    

    rpm = 100
    fpm = 100
    par.loc[pst.par_names[1:],"partrans"] = "fixed"
    par.loc[pst.par_names[1:],"parchglim"] = "factor"
    par.loc[pst.par_names[0],"partrans"] = "none"
    par.loc[pst.par_names[0],"parlbnd"] = 0.9
    par.loc[pst.par_names[0],"parubnd"] = 1.1   
    par.loc[pst.par_names[0],"parchglim"] = "relative"
    par.loc[pst.par_names[0],"parval1"] = 1.0
    pst.control_data.relparmax = rpm
    pst.control_data.facparmax = fpm
    
    pst.write(os.path.join(m_d,"pest_parchglim.pst"))
    pyemu.os_utils.run("{0} pest_parchglim.pst".format(exe_path.replace("-ies","-glm")),cwd=m_d)
    p_df = pyemu.pst_utils.read_parfile(os.path.join(m_d,"pest_parchglim.par"))
    print(p_df)
    assert p_df.loc["stage","parval1"] == par.loc["stage","parubnd"]

    
def sen_plusplus_test():
    model_d = "ies_10par_xsec"
    local=True
    if "linux" in platform.platform().lower() and "10par" in model_d:
        #print("travis_prep")
        #prep_for_travis(model_d)
        local=False
    
    t_d = os.path.join(model_d,"template")
    m_d = os.path.join(model_d,"master_sen_plusplus")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    pst = pyemu.Pst(os.path.join(t_d,"pest.pst"))
    pst.pestpp_options = {}
    pst.pestpp_options["gsa_method"] = "morris"
    pst.pestpp_options["gsa_sobol_samples"] = 50
    pst.pestpp_options["gsa_sobol_par_dist"] = "unif"
    pst.pestpp_options["gsa_morris_r"] = 4
    pst.pestpp_options["gsa_morris_p"] = 5
    pst.pestpp_options["gsa_morris_delta"] = 2
    pst.write(os.path.join(t_d,"pest_sen.pst"))
    pyemu.os_utils.start_slaves(t_d, exe_path.replace("-ies","-sen"), "pest_sen.pst", 5, master_dir=m_d,
                           slave_root=model_d,local=local,port=port)

def new_fmt_test1():
    model_d = "ies_10par_xsec"
    local=True
    if "linux" in platform.platform().lower() and "10par" in model_d:
        #print("travis_prep")
        #prep_for_travis(model_d)
        local=False
    
    t_d = os.path.join(model_d,"template")
    m_d = os.path.join(model_d,"master_newpstfmt")
    if os.path.exists(m_d):
        shutil.rmtree(m_d)
    shutil.copytree(t_d,m_d)
    pst = pyemu.Pst(os.path.join(m_d,"pest.pst"))
    pst.write(os.path.join(m_d,"pest_new.pst"),version=2)

if __name__ == "__main__":
    new_fmt_test1()
    #sen_plusplus_test()
    #parchglim_test()
    #unc_file_test()

    #basic_test("ies_10par_xsec")
    #glm_save_binary_test()
    #sweep_forgive_test()
    #inv_regul_test()
    #tie_by_group_test()
