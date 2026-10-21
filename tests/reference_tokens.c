// Independent reference: upstream karpathy/llama2.c (MIT), unmodified run.c.
#define main upstream_main
#include "reference_run.c"
#undef main

int main(int argc, char **argv) {
    if (argc != 5) return 2;
    Transformer model;
    Tokenizer tokenizer;
    build_transformer(&model, argv[1]);
    build_tokenizer(&tokenizer, argv[2], model.config.vocab_size);
    int prompt[4096], length=0, count=atoi(argv[4]);
    encode(&tokenizer, argv[3], 1, 0, prompt, &length);
    printf("{\"prompt_tokens\":[");
    for (int i=0;i<length;i++) printf("%s%d",i?",":"",prompt[i]);
    printf("],\"first_logits\":[");
    float *logits=NULL;
    for (int i=0;i<length;i++) logits=forward(&model,prompt[i],i);
    for (int i=0;i<model.config.vocab_size;i++) printf("%s%.9g",i?",":"",logits[i]);
    printf("],\"generated_tokens\":[");
    for (int i=0;i<count;i++) {
        int next=sample_argmax(logits,model.config.vocab_size);
        printf("%s%d",i?",":"",next);
        if (next==1 || next==2) break;
        if (i+1<count) logits=forward(&model,next,length+i);
    }
    printf("]}\n");
    free_transformer(&model);
    free_tokenizer(&tokenizer);
    return 0;
}
