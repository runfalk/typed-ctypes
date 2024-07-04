#![allow(clippy::missing_safety_doc)]
macro_rules! impl_tuple {
    ($struct_name:ident, $swap_fn:ident, $type:ty) => {
        #[repr(C)]
        pub struct $struct_name {
            pub a: $type,
            pub b: $type,
        }

        #[no_mangle]
        pub unsafe extern "C" fn $swap_fn(s: *mut $struct_name) {
            let s = &mut *s;
            std::mem::swap(&mut s.a, &mut s.b);
        }
    };
}

macro_rules! impl_sub {
    ($name:ident, $type:ty) => {
        #[no_mangle]
        pub unsafe extern "C" fn $name(x: $type, y: $type) -> $type {
            x - y
        }
    };
}

impl_tuple!(U8Tuple, swap_u8_tuple, u8);
impl_tuple!(U16Tuple, swap_u16_tuple, u16);
impl_tuple!(U32Tuple, swap_u32_tuple, u32);
impl_tuple!(U64Tuple, swap_u64_tuple, u64);
impl_tuple!(I8Tuple, swap_i8_tuple, i8);
impl_tuple!(I16Tuple, swap_i16_tuple, i16);
impl_tuple!(I32Tuple, swap_i32_tuple, i32);
impl_tuple!(I64Tuple, swap_i64_tuple, i64);
impl_tuple!(F32Tuple, swap_f32_tuple, f32);
impl_tuple!(F64Tuple, swap_f64_tuple, f64);

impl_sub!(sub_u8, u8);
impl_sub!(sub_u16, u16);
impl_sub!(sub_u32, u32);
impl_sub!(sub_u64, u64);
impl_sub!(sub_i8, i8);
impl_sub!(sub_i16, i16);
impl_sub!(sub_i32, i32);
impl_sub!(sub_i64, i64);
impl_sub!(sub_f32, f32);
impl_sub!(sub_f64, f64);
