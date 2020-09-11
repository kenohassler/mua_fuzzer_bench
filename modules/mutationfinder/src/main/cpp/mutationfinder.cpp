#include <iostream>
#include <fstream>
#include <map>
#include <thread>

#include "pattern_lib.h"

#include <llvm/Pass.h>
#include <llvm/IR/Type.h>
#include <llvm/IR/Module.h>
#include <llvm/IR/IntrinsicInst.h>
#include <llvm/IR/Function.h>
#include <llvm/Support/raw_ostream.h>
#include <llvm/Support/CommandLine.h>



using namespace llvm;

#define DEBUG_TYPE "mutationfinder"

cl::opt<std::string> MutationLocationFile("mutation_patterns",
                                   cl::desc("file containing the mutation patterns"),
                                   cl::value_desc("filename"));

// a counter and the number of functions to print the current status
int number_functions = 0;
int funcounter = 0;

std::ofstream mutationLocations;

class Worker
{
private:

    std::mutex& builderMutex;
    std::mutex& fileMutex;
    llvm::Module& M;

public:

    explicit Worker() = delete;

    Worker(Module& M, std::mutex& builderMutex, std::mutex& fileMutex)
        : builderMutex(builderMutex)
        , fileMutex(fileMutex)
        , M(M)
    {

    }

    /**
     * Instrument all functions given as parameter.
     * @param functions
     */
    void findPatternInFunctions(std::vector<Function*> functions)
    {
        for (auto F: functions)
        {
            builderMutex.lock();
            std::cout << "[INFO] in thread " << std::this_thread::get_id() << ": "
                      << "instrumenting function " << ++funcounter << " of " << number_functions
                      << ": " << F->getName().data()
                      << std::endl;
            builderMutex.unlock();
            findPatternInFunction(*F);
        }
    }




    /**
     * Instrument the given instruction with the given builders.
     * @param instr
     * @param builder
     * @param nextInstructionBuilder
     */
    void handInstructionToPatternMatchers(Instruction* instr)
    {
        // Handle call instructions with function call pattern analyzer
        if (auto* callinst = dyn_cast<CallInst>(instr))
        {
            Function* fun = callinst->getCalledFunction();
            if (fun != nullptr && fun->isIntrinsic() && !dyn_cast<MemCpyInst>(callinst) && !dyn_cast<MemMoveInst>(callinst)
                && !dyn_cast<VAStartInst>(callinst) && !dyn_cast<VAArgInst>(callinst) && !dyn_cast<VACopyInst>(callinst)
                && !dyn_cast<VAEndInst>(callinst))
            {
                // skip llvm intrinsic functions other than llvm.memcpy and llvm memmove
                return;
            }

            auto patternLocations = look_for_pattern(instr);
            for (auto loc: patternLocations) {
                fileMutex.lock();
                mutationLocations << loc;
                fileMutex.unlock();
            }
            return;
        }
    }


    /**
     * Instrument one function, i.e. run over all instructions in that function and instrument them.
     * @param F the given function
     * @return true on successful instrumentation
     */
    bool findPatternInFunction(Function& F)
    {
        std::vector<Instruction*> toInstrument;
        for (BasicBlock& bb : F)
        {
            auto first_insertion_point = bb.getFirstInsertionPt();

            for (BasicBlock::iterator itr_bb = first_insertion_point; itr_bb != bb.end(); ++itr_bb)
            {
                toInstrument.push_back(&*itr_bb);
            }
        }

        for (Instruction* instr : toInstrument)
        {
            handInstructionToPatternMatchers(instr);
        }

        return true;
    }
};

struct MutatorPlugin : public ModulePass
{
    static char ID; // Pass identification, replacement for typeid
    MutatorPlugin() : ModulePass(ID) {}

    bool runOnModule(Module& M) override
    {
        auto& llvm_context = M.getContext();

        // TODO read mutation patterns



        std::mutex builderMutex;
        std::mutex fileMutex;
        mutationLocations.open(MutationLocationFile);
        unsigned int concurrentThreadsSupported = ceil(std::thread::hardware_concurrency() * 30);
        std::cout << "[INFO] number of threads: " << concurrentThreadsSupported << std::endl;

        std::vector<std::vector<Function*>> threadFunctions(concurrentThreadsSupported);
        auto i = 0;
        for (Function& f : M.functions())
        {
            if (f.isDeclaration())
            {
                continue;
            }

            threadFunctions[i % concurrentThreadsSupported].push_back(&f);
            ++i;
        }

        number_functions = i;
        std::vector<std::thread> threads;
        for (auto& functions : threadFunctions)
        {
            threads.push_back(std::thread(&Worker::findPatternInFunctions, new Worker(M, builderMutex, fileMutex), functions));
        }

        for (auto& thread : threads)
        {
            thread.join();
        }

        mutationLocations.close();
        return true;
    }
};

char MutatorPlugin::ID = 0;
static RegisterPass<MutatorPlugin> X("mutationfinder", "Plugin to mutate a bitcode file.");
