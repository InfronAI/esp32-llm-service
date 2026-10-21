#include "py/dynruntime.h"
#include "transformer.h"

// newlib libm expects errno storage. Inference is serialized, and no caller
// relies on libm errno; provide module-owned storage without importing an RTOS.
int tinyllm_errno;
int *__errno(void) { return &tinyllm_errno; }

// Limit this module to the checked checkpoint layout. Malformed buffers must
// raise a Python error rather than allowing unchecked native memory accesses.
static Config *checked_model(mp_obj_t obj, mp_buffer_info_t *buffer) {
    mp_get_buffer_raise(obj, buffer, MP_BUFFER_READ);
    if (buffer->len != 1056540 || ((uintptr_t)buffer->buf & 3)) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid stories260K checkpoint size/alignment"));
    }
    Config *p=buffer->buf;
    if (p->dim!=64 || p->hidden_dim!=172 || p->n_layers!=5 || p->n_heads!=8 ||
        p->n_kv_heads!=4 || p->vocab_size!=512 || p->seq_len!=512) {
        mp_raise_ValueError(MP_ERROR_TEXT("unsupported model configuration"));
    }
    return p;
}

static size_t state_floats(const Config *p) {
    int kv=p->dim*p->n_kv_heads/p->n_heads;
    return 4*p->dim+2*p->hidden_dim+2*p->n_layers*p->seq_len*kv+
           p->n_heads*p->seq_len+p->vocab_size;
}

static mp_obj_t state_size(mp_obj_t model) {
    mp_buffer_info_t b;
    return mp_obj_new_int(state_floats(checked_model(model,&b)));
}
static MP_DEFINE_CONST_FUN_OBJ_1(state_size_obj,state_size);

static mp_obj_t infer(size_t nargs, const mp_obj_t *args) {
    mp_buffer_info_t model,state;
    Config *p=checked_model(args[0],&model);
    mp_get_buffer_raise(args[1],&state,MP_BUFFER_WRITE);
    int token=mp_obj_get_int(args[2]), pos=mp_obj_get_int(args[3]);
    if (state.len!=state_floats(p)*sizeof(float) || ((uintptr_t)state.buf & 3) ||
        token<0 || token>=p->vocab_size || pos<0 || pos>=p->seq_len) {
        mp_raise_ValueError(MP_ERROR_TEXT("invalid state, token or context position"));
    }
    Transformer t;
    t.config=*p;
    memory_map_weights(&t.weights,p,(float*)((char*)model.buf+sizeof(Config)),1);
    float *ptr=state.buf;
    t.state.x=ptr; ptr+=p->dim;
    t.state.xb=ptr; ptr+=p->dim;
    t.state.xb2=ptr; ptr+=p->dim;
    t.state.hb=ptr; ptr+=p->hidden_dim;
    t.state.hb2=ptr; ptr+=p->hidden_dim;
    t.state.q=ptr; ptr+=p->dim;
    int cache=p->n_layers*p->seq_len*(p->dim*p->n_kv_heads/p->n_heads);
    t.state.key_cache=ptr; ptr+=cache;
    t.state.value_cache=ptr; ptr+=cache;
    t.state.att=ptr; ptr+=p->n_heads*p->seq_len;
    t.state.logits=ptr;
    forward(&t,token,pos);
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(infer_obj,4,4,infer);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self,size_t n_args,size_t n_kw,mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_state_size,MP_OBJ_FROM_PTR(&state_size_obj));
    mp_store_global(MP_QSTR_forward,MP_OBJ_FROM_PTR(&infer_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
