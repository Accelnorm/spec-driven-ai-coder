use bytemuck::{Pod, Zeroable};
use solana_program::pubkey::Pubkey;
use spl_pod::primitives::PodU64;

/// The vault account data structure.
/// This is a fixed-layout POD struct suitable for on-chain storage.
#[repr(C)]
#[derive(Copy, Clone, Debug, Default, Pod, Zeroable)]
pub struct Vault {
    /// The vault owner (authority)
    pub owner: Pubkey,
    /// Total shares outstanding
    pub shares_total: PodU64,
    /// Total tokens in vault
    pub token_total: PodU64,
}

impl Vault {
    /// Create a new vault with the given owner
    pub fn new(owner: Pubkey) -> Self {
        Vault {
            owner,
            shares_total: PodU64::from(0),
            token_total: PodU64::from(0),
        }
    }
}
