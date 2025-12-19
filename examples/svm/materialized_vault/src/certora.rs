//! Formal verification module for the vault.

pub mod spec;

/// Macro to assume the solvency property holds.
/// Solvency: shares_total <= token_total
#[macro_export]
macro_rules! assume_solvency {
    ($fv_vault:expr) => {
        cvlr::cvlr_assume!($fv_vault.shares_total <= $fv_vault.token_total);
    };
}

/// Macro to assert the solvency property holds.
/// Solvency: shares_total <= token_total
#[macro_export]
macro_rules! assert_solvency {
    ($fv_vault:expr) => {
        cvlr::cvlr_assert!($fv_vault.shares_total <= $fv_vault.token_total);
    };
}
